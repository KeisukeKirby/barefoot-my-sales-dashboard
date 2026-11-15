# -*- coding: utf-8 -*-
u"""KL ポップアップに持ち出した在庫を Order Sheet の xlsx から拾って kl_stock.json を書く。

    python build_kl.py "BFMY 2nd pop up event in KL 13-15Nov stock list2.xlsx"

Order Sheet はサイズが横に並ぶマトリクスで、こちらの SKU とは呼び方が違う:
  * 性別は Style# の接頭辞(26M…/26W…)か、その欄に直接書かれた Men/Women/Unisex。
    サイズ列(35#〜47#)は男女で共通なので、行ごとに判定してから W38 / M43 / U42 に直す。
  * カラー名も表記が違う(Ivory-Deep Lake / Fuschia / V-Aplha など)。下の表で寄せる。
ソックス(2枚目のシート)はサイズが S / M / L で、cm 表記の幅が商品ごとに違う。
Oleno はこちらの在庫側が 25 / 27 / 29 なので読み替える。

突き合わせは (model, color, size) の3点。合わなかった行は必ず警告を出す
(黙って0足にすると JB 在庫が過大になり、持ち出したはずの靴が JB にあることになる)。
"""
import io
import json
import os
import sys

import xlsxread

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'kl_stock.json')

# (シートの Style Name, シートの Color Description) -> (こちらの model, color)
MAP = {
    (u'Groundsplay LS', u'Total Black'):      (u'Groundsplay LS', u'Black'),
    (u'Groundsplay LS', u'Ivory-Deep Lake'):  (u'Groundsplay LS', u'Ivory/Deep Lake'),
    (u'Spidrwalk', u'Total Black'):           (u'Spidrwalk', u'Total Black'),
    (u'Spidrwalk', u'Lime'):                  (u'Spidrwalk', u'Lime Green'),
    (u'Spidrwalk', u'Fuschia'):               (u'Spidrwalk', u'Fuchsia'),
    (u'Breezandal', u'Black'):                (u'Breezandal', u'Black'),
    (u'Breezandal', u'Ivory/Green'):          (u'Breezandal', u'Ivory/Green'),
    (u'V-Soul', u'Black'):                    (u'V-Soul', u'Black'),
    (u'V-Soul', u'Brown'):                    (u'V-Soul', u'Brown'),
    (u'V-Soul', u'Baby Blue'):                (u'V-Soul', u'Baby Blue'),
    (u'V-Run', u'Total Black'):               (u'V-Run', u'Total Black'),
    (u'V-Run', u'Black-Lime/Black'):          (u'V-Run', u'Black-Lime'),
    (u'V-Run', u'Fig/Brown/A.Green'):         (u'V-Run', u'Fig/Ivory/Green'),
    (u'Trailope', u'Black'):                  (u'Trailope', u'Black'),
    (u'KSO EVO', u'Black'):                   (u'KSO EVO', u'Black'),
    (u'KSO EVO', u'Deep Lake'):               (u'KSO EVO', u'Deep Lake'),
    (u'V-Aplha', u'Deep Lake'):               (u'V-Alpha', u'Deep Lake'),
    (u'Scramkey', u'Black'):                  (u'Scramkey', u'Black'),
    (u'Scramkey', u'Black/Deep Lake'):        (u'Scramkey', u'Deep Lake'),
    # 足袋は同じシートの2つ目の表。サイズが cm 直書きで男女の別が無い。
    (u'Marugo Tabirela', u'Moon'):            (u'tabiRela', u'Tsuki/Moon'),
    (u'Marugo Tabirela', u'Lemon'):           (u'tabiRela', u'Lemon'),
    (u'Marugo Tabirela', u'Ocean'):           (u'tabiRela', u'Umi/Ocean'),
    (u'Marugo Hitoe+', u'Zebra/White'):       (u'Hitoe+', u'Zebra White'),
    (u'Marugo Hitoe+', u'Zebra/Navy'):        (u'Hitoe+', u'Zebra Navy'),
    # ソックス側は Brand + Style Name で引く
    (u'Ultimate', u'Black'):                  (u'Oleno Ultimate', u'Black'),
    (u'Ultimate ASO', u'Black'):              (u'Oleno Ultimate Aso', u'Black'),
    (u'Ultimate TNG', u'Black x Gray'):       (u'Oleno Ultimate TNG', u'Black/Gray'),
    (u'Ultimate TNG', u'Black x Blue'):       (u'Oleno Ultimate TNG', u'Black/Blue'),
    (u'5-toes Socks', u'Black'):              (u'Barefootinc.Jp Socks', u'Black'),
    (u'5-toes Socks', u'Gray'):               (u'Barefootinc.Jp Socks', u'Gray'),
}

# ソックスのサイズ列 -> こちらのサイズ。モデルごとに呼び方が違う。
SOCKSIZE = {
    u'Oleno Ultimate':        {'S': u'25', 'M': u'27', 'L': u'29'},
    u'Oleno Ultimate Aso':    {'S': u'25', 'M': u'27', 'L': u'29'},
    u'Oleno Ultimate TNG':    {'S': u'25', 'M': u'27', 'L': u'29'},
    u'Barefootinc.Jp Socks':  {'S': u'S', 'M': u'M', 'L': u'L'},
}


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def sex(style):
    """Style# 欄から W / M / U を決める。"""
    s = (style or '').strip()
    low = s.lower()
    if low.startswith('men') or low == 'm':
        return 'M'
    if low.startswith('women') or low == 'w':
        return 'W'
    if low.startswith('unisex'):
        return 'U'
    # 26M3201 / 25W4302 のような型番
    for ch in s[:4].upper():
        if ch in ('M', 'W'):
            return ch
    return None


def sizecols(head):
    """ヘッダ行からサイズ列を拾う。'35#' なら男女別(接頭辞が付く)、'23.5' ならそのまま。"""
    pre, cols = False, []
    for i, c in enumerate(head):
        c = (c or '').strip()
        if c.endswith('#') and c[:-1].strip().replace('.', '', 1).isdigit():
            pre = True
            cols.append((i, c[:-1].strip()))
        elif c.replace('.', '', 1).isdigit():
            cols.append((i, c))
    return pre, cols


def shoes(rows, out, warn):
    """VFF シートは表が2つ縦に並ぶ(VFF本体と足袋)。ヘッダが出たら列を切り替える。"""
    pre, cols = False, []
    for r in rows:
        if not r or len(r) < 6:
            continue
        if r[0] and r[0].strip() == 'Style Name':
            pre, cols = sizecols(r)
            continue
        if not cols:
            continue
        name, style, color = (r[0] or '').strip(), (r[1] or '').strip(), (r[2] or '').strip()
        if not name or not color:
            continue
        key = MAP.get((name, color))
        if not key:
            warn.append(u'VFF: 対応表に無い行 %s / %s' % (name, color))
            continue
        g = ''
        if pre:
            g = sex(style)
            if not g:
                warn.append(u'VFF: 男女が読めない行 %s / %s / Style#=%s' % (name, color, style))
                continue
        for i, sz in cols:
            q = num(r[i]) if i < len(r) else 0
            if q:
                k = (key[0], key[1], g + sz)
                out[k] = out.get(k, 0) + q


def socks(rows, out, warn):
    head = None
    for r in rows:
        if r and r[0] == 'Brand':
            head = r
            break
    if head is None:
        warn.append(u'Socks シートのヘッダ行(Brand)が見つかりません')
        return
    # 'S\n23-25cm' のような列。頭文字がサイズ。
    cols = [(i, c.strip()[0].upper()) for i, c in enumerate(head)
            if c and c.strip()[0].upper() in ('S', 'M', 'L') and 'cm' in c]
    for r in rows:
        if not r or r[0] == 'Brand' or len(r) < 7:
            continue
        name, color = (r[1] or '').strip(), (r[3] or '').strip()
        if not name or not color:
            continue
        key = MAP.get((name, color))
        if not key:
            warn.append(u'Socks: 対応表に無い行 %s / %s' % (name, color))
            continue
        tbl = SOCKSIZE.get(key[0], {})
        for i, sz in cols:
            q = num(r[i]) if i < len(r) else 0
            if not q:
                continue
            our = tbl.get(sz)
            if not our:
                warn.append(u'Socks: サイズが読み替えられません %s %s' % (key[0], sz))
                continue
            k = (key[0], key[1], our)
            out[k] = out.get(k, 0) + q


def main():
    if len(sys.argv) < 2:
        sys.exit(u'KL のオーダーシート xlsx を渡してください')
    path = sys.argv[1]
    out, warn = {}, []
    shoes(xlsxread.read(path, 'xl/worksheets/sheet1.xml'), out, warn)
    socks(xlsxread.read(path, 'xl/worksheets/sheet2.xml'), out, warn)

    items = [dict(model=m, color=c, size=s, qty=q)
             for (m, c, s), q in sorted(out.items())]
    json.dump(dict(meta=dict(src=os.path.basename(path), rows=len(items),
                             total=sum(i['qty'] for i in items), warn=warn),
                   items=items),
              io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

    print(u'KL 持ち出し %d 行 / %d足' % (len(items), sum(i['qty'] for i in items)))
    for w in warn:
        print(u'  !! ' + w)
    print(u'  続けて build_payload.py を回すと在庫表に反映されます。')


if __name__ == '__main__':
    main()
