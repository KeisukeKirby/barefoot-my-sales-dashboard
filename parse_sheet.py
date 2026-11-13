# -*- coding: utf-8 -*-
"""Drive の "Sales record for Malaysia.xlsx" をテキスト化したもの(sheet_raw.txt)を
行に切り直して sheet.json を書く。

テキスト化の過程で「行の最終セル」と「次行の No.」が空白1つで連結されているため、
列数を前提に境界フィールドを割り直している。

列数はシートごとに違う。Nov2026 から備考列が1本増えて 16 列になったので、
見出し行の空セル数からシートごとに数える。COLS は先頭15列だけ使い、
16列目以降(備考)は落とす。
"""
import csv, io, json, os, re

HERE = os.environ.get('SHEET_WORKDIR', os.path.dirname(os.path.abspath(__file__)))
COLS = ['no', 'oid', 'date', 'ch', 'cust', 'frm', 'pay', 'addr', 'prod', 'price',
        'walkin', 'online', 'courier', 'track', 'contact', 'last']
# 見出しの文言 -> 内部キー。位置ではなく名前で引く。
# Nov2026 で 2列目に SiteGiant Order \# が挿され、位置固定だと全部ずれたため。
HEAD2KEY = {
    'No.': 'no', 'SiteGiant Order #': 'oid', 'Date': 'date', 'Channel': 'ch',
    'Customer Name': 'cust', 'From': 'frm', 'Payment Details': 'pay', 'Address': 'addr',
    'Product': 'prod', 'Price(RM)': 'price', 'Walk in': 'walkin', 'Walk In': 'walkin',
    'Online sales': 'online', 'Courier': 'courier',
    'Tracking No.': 'track', 'Tracking No/Remarks': 'track',
    'Contact #': 'contact', 'Note': 'last', 'Number of Vibram sold': 'last',
}
TITLE = 'Johor Bahru Sale record 2026'


def split_boundary(b, nx2):
    # 次がヘッダ行。2列目は 'Date' とは限らない(Nov2026 から 'SiteGiant Order #')
    if b.strip().endswith('No.') and nx2 in HEAD2KEY:
        return b[:-3].strip(), 'No.'
    if nx2 == 'TOTAL':
        return b, ''
    m = re.search(r'(\S+ ' + TITLE + r')$', b)   # 前の行の末尾 + 次のシートの見出し
    if m:
        return b[:m.start()].strip(), m.group(1)
    if b.endswith(TITLE):
        return '', b
    if b.isdigit():
        return '', b
    m = re.match(r'^(.*?)\s+(\d+)$', b)
    if m:
        return m.group(1), m.group(2)
    return b, ''


def sheet_strides(F):
    """[(見出しの位置, そのシートの列数)]。見出し行の後ろに並んでいる
    空セルを数える。その次に来るのはヘッダ行の 'No.' が境界で混じったフィールド。"""
    out = []
    for i, f in enumerate(F):
        if f.endswith(TITLE):
            j = i + 1
            while j < len(F) and F[j] == '':
                j += 1
            out.append((i, (j - i - 1) + 2))
    return out


def money(s):
    s = (s or '').replace('RM', '').replace(',', '').strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def main():
    raw = io.open(os.path.join(HERE, 'sheet_raw.txt'), encoding='utf-8').read()
    F = [f.strip() for f in next(csv.reader([raw]))]
    strides = sheet_strides(F)
    assert strides and strides[0][0] == 0, strides

    rows, carry, i, si = [], F[0], 0, 0
    while i + 1 < len(F):
        while si + 1 < len(strides) and i >= strides[si + 1][0]:
            si += 1
        step = strides[si][1] - 1          # 1行あたりのフィールド数
        end = i + step
        if end >= len(F) - 1:
            # 最終行。次の行がないので境界の割り直しはしない
            rows.append([carry] + F[i + 1:])
            break
        last, nxt = split_boundary(F[end], F[end + 1])
        rows.append([carry] + F[i + 1: end] + [last])
        carry = nxt
        i = end
    R = len(rows)

    out, sheet, hmap, tot = [], None, None, {}
    for cells in rows:
        first = cells[0] if cells else ''
        if first.endswith(TITLE):
            sheet, hmap = first.split()[0], None
            continue
        if first == 'No.':
            # そのシートの列位置を見出しから読む。知らない見出しは無視する
            hmap = {}
            for j, h in enumerate(cells):
                k = HEAD2KEY.get(h.strip())
                if k and k not in hmap:
                    hmap[k] = j
            miss = [k for k in ('no', 'date', 'ch', 'frm', 'prod') if k not in hmap]
            assert not miss, (sheet, miss, cells[:6])
            continue
        if sheet is None or hmap is None:
            continue
        d = {k: (cells[j] if j < len(cells) else '') for k, j in hmap.items()}
        for k in COLS:
            d.setdefault(k, '')
        if d['date'] == 'TOTAL':
            tot[sheet] = (money(d['ch']), money(d['walkin']), money(d['online']))
            continue
        if not any(v for k, v in d.items() if k not in ('no', 'oid')):
            continue
        d['sheet'] = sheet
        out.append(d)

    json.dump(out, io.open(os.path.join(HERE, 'sheet.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('rows=%d  data=%d' % (R, len(out)))
    seen = []
    for x in out:                       # シートは出てきた順に出す
        if x['sheet'] not in seen:
            seen.append(x['sheet'])
    for s in seen:
        n = [x for x in out if x['sheet'] == s]
        w = round(sum(money(x['walkin']) or 0 for x in n), 2)
        o = round(sum(money(x['online']) or 0 for x in n), 2)
        p = round(sum(money(x['price']) or 0 for x in n), 2)
        t = tot[s]
        print('%-9s rows=%3d  walkin %10.2f (sheet %10.2f)  online %9.2f (sheet %9.2f)  price %10.2f (sheet total %10.2f)'
              % (s, len(n), w, t[1], o, t[2], p, t[0]))
    return out


if __name__ == '__main__':
    main()
