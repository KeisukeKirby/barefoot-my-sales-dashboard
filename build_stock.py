# -*- coding: utf-8 -*-
"""SiteGiant の stock_movement エクスポートから現在庫の土台を作り、stock.json を書く。

    python build_stock.py "<stock_movement_*.xlsx>" ["<追加の xlsx>" ...]

SiteGiant には「現在庫の一覧」エクスポートが無く、在庫の増減ログしか出せない。
各 SKU の最後の記録の `to` が現在の値なので、そこから現在庫を組み立てる。

ログは Recent(直近) と Archived(それ以前) に分かれていて、期間も選ぶ必要がある。
開業前から今日まで全部渡すこと。9月以降しか渡さないと、それ以降まったく動いて
いない商品(= 死に在庫。いちばん知りたいもの)が丸ごと抜ける。

数量は3種類ある:
  Stock On Hand      実際に手元にある数
  Sellable Stock     売れる数。受注が立つと減る
  Non Sellable Stock 受注済み・未出荷の引当分。出荷(Release)で0に戻る
画面の「在庫」はこの Sellable。2026-11-15 のエクスポートで管理画面の表示と5/5一致を確認済み。

ここが出すのは在庫の土台だけで、販売実績とは結ばない。
販売は毎週更新されるが在庫エクスポートは毎回もらえるとは限らないので、
「土台 - 基準日より後に売れた分」の差し引きは build_payload.py 側でやる。
そうしておけば、販売実績だけ更新しても在庫がその分減る。
"""
import io
import json
import os
import sys

import xlsxread
from skumeta import COLORNAME, MODEL, USE_OF, USE_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'stock.json')
# レディースは W43 まで。W44 以降は SiteGiant 側に枠だけあるサイズで、
# 在庫も販売も無い(2026-11-15 Keisuke)。万が一中身が入ったら警告を出す。
WMAX = 43


def nsize(s):
    """サイズ表記のゆれを吸収する。足袋は注文側が '24cm'、在庫側が '24'。"""
    return (s or '').replace('cm', '').replace('CM', '').strip()


def parse_sku(sku):
    """VFF0008(BR,W36) -> (model, brand, cat, color, size)"""
    for pre, model, brand, cat in MODEL:
        if sku.startswith(pre):
            break
    else:
        return (sku[:30], u'その他', 'other', u'(不明)', u'(不明)')
    color = size = None
    if '(' in sku and sku.endswith(')'):
        body = sku[sku.index('(') + 1:-1]
        if ',' in body:
            c, s = body.split(',', 1)
            color, size = c.strip(), s.strip()
    return (model, brand, cat,
            COLORNAME.get(color, color) if color else u'(色の記録なし)',
            size or u'(サイズなし)')


def load(paths):
    rows = []
    for p in paths:
        rs = xlsxread.read(p)
        if not rs:
            continue
        head = rs[0]
        for r in rs[1:]:
            d = dict(zip(head, r))
            if d.get('isku'):
                rows.append(d)
    return rows


def main():
    paths = sys.argv[1:]
    if not paths:
        sys.exit(u'stock_movement の xlsx を渡してください（Recent と Archived の両方）')
    rows = load(paths)
    if not rows:
        sys.exit(u'行が1つも読めませんでした')

    last = {}
    for r in rows:
        k = (r['isku'], r['stock_type'])
        if k not in last or r['date'] > last[k]['date']:
            last[k] = r
    skus = sorted({r['isku'] for r in rows})
    asof_ts = max(r['date'] for r in rows)[:16]   # 'YYYY-MM-DD HH:MM'
    asof = asof_ts[:10]

    def q(sku, t):
        r = last.get((sku, t))
        try:
            return int(float(r['to'])) if r else 0
        except (TypeError, ValueError):
            return 0

    items = []
    for s in skus:
        model, brand, cat, color, size = parse_sku(s)
        items.append(dict(
            sku=s, model=model, brand=brand, cat=cat, color=color, size=size,
            use=USE_OF.get(model, u'その他'),
            sellable=q(s, 'Sellable Stock'), onhand=q(s, 'Stock On Hand'),
            reserved=q(s, 'Non Sellable Stock'),
            last_move=last.get((s, 'Stock On Hand'),
                               last.get((s, 'Sellable Stock'), {})).get('date', '')[:10],
        ))

    def over(it):
        if not it['size'].startswith('W'):
            return False
        try:
            return float(it['size'][1:]) > WMAX
        except ValueError:
            return False

    drop = [i for i in items if over(i)]
    items = [i for i in items if not over(i)]
    live = [i for i in drop if i['sellable']]
    if live:
        print(u'!! W%d を超えるレディースサイズに在庫があります。WMAX を見直してください:' % WMAX)
        for i in live:
            print(u'   %s %s %s 在庫%d' % (i['model'], i['color'], i['size'], i['sellable']))

    out = dict(
        meta=dict(asof=asof, asof_ts=asof_ts, src=[os.path.basename(p) for p in paths],
                  skus=len(items), dropped=len(drop), wmax=WMAX,
                  use_order=USE_ORDER),
        items=items)
    json.dump(out, io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

    print(u'在庫基準日 %s / SKU %d / 販売可 %d足 / 実在庫 %d足 (W%d 超を %d SKU 除外)'
          % (asof, len(items), sum(i['sellable'] for i in items),
             sum(i['onhand'] for i in items), WMAX, len(drop)))
    print(u'  在庫ゼロ %d SKU / 引当中 %d足'
          % (sum(1 for i in items if i['sellable'] == 0),
             sum(i['reserved'] for i in items)))
    print(u'  販売との突き合わせは build_payload.py が行います。続けて回してください。')


if __name__ == '__main__':
    main()
