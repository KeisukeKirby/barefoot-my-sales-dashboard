# -*- coding: utf-8 -*-
"""SiteGiant の stock_movement エクスポートから現在庫を作り、stock.json を書く。

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
"""
import collections
import datetime
import io
import json
import os
import sys

import xlsxread
from skumeta import COLORNAME, MODEL, USE_OF, USE_ORDER

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'stock.json')
QTY = ('Stock On Hand', 'Sellable Stock', 'Non Sellable Stock')
# 直近の販売ペースを測る窓。短すぎると1件の売れ方に振られ、長すぎると今の勢いが出ない
WEEKS = 4


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
    asof = max(r['date'] for r in rows)[:10]

    def q(sku, t):
        r = last.get((sku, t))
        try:
            return int(float(r['to'])) if r else 0
        except (TypeError, ValueError):
            return 0

    # --- 販売実績を足す。直近の売れ方が無いと在庫数だけ見ても判断できない
    A = json.load(io.open(os.path.join(HERE, 'agg.json'), encoding='utf-8'))
    S = [o for o in A['orders'] if o['bucket'] == 'sales']
    dmax = max(o['date'] for o in S)
    cut = (datetime.date(*map(int, dmax.split('-')))
           - datetime.timedelta(days=7 * WEEKS)).isoformat()
    # SKU ではなく モデル×カラー×サイズ で突き合わせる。
    # Marugo は注文エクスポートが Marugo Tab-2119、在庫が MTB0001(DN,24) と
    # 型番体系が違うため、SKU で結ぶと Marugo が丸ごと落ちる。
    sold_all = collections.Counter()
    sold_recent = collections.Counter()
    lastsold = {}
    for o in S:
        for it in o['items']:
            if it['cat'] not in ('shoes', 'socks'):
                continue
            k = (it['model'], it['color'] or u'(色の記録なし)', nsize(it['size']) or u'(サイズなし)')
            sold_all[k] += it['qty']
            if o['date'] > cut:
                sold_recent[k] += it['qty']
            if k not in lastsold or o['date'] > lastsold[k]:
                lastsold[k] = o['date']

    items = []
    for s in skus:
        model, brand, cat, color, size = parse_sku(s)
        sell, onhand = q(s, 'Sellable Stock'), q(s, 'Stock On Hand')
        key = (model, color, nsize(size))
        rec = sold_recent.get(key, 0)
        per_week = rec / float(WEEKS)
        items.append(dict(
            sku=s, model=model, brand=brand, cat=cat, color=color, size=size,
            use=USE_OF.get(model, u'その他'),
            sellable=sell, onhand=onhand, reserved=q(s, 'Non Sellable Stock'),
            sold_all=sold_all.get(key, 0), sold_recent=rec,
            per_week=round(per_week, 2),
            # 在庫週数。売れていない商品は「何週もつか」が無限になるので None にする
            weeks=round(sell / per_week, 1) if per_week > 0 else None,
            last_sold=lastsold.get(key),
            last_move=last.get((s, 'Stock On Hand'), last.get((s, 'Sellable Stock'), {})).get('date', '')[:10],
        ))

    # 販売実績にあるのに在庫表に無い組み合わせ
    have = {(i['model'], i['color'], nsize(i['size'])) for i in items}
    unmatched = sorted(u'%s / %s / %s' % k for k in sold_all if k not in have)

    out = dict(
        meta=dict(asof=asof, src=[os.path.basename(p) for p in paths],
                  skus=len(items), weeks=WEEKS, sales_until=dmax,
                  use_order=USE_ORDER, unmatched_sku=unmatched),
        items=items)
    json.dump(out, io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)

    tot_sell = sum(i['sellable'] for i in items)
    print(u'在庫基準日 %s / SKU %d / 販売可 %d足 / 実在庫 %d足'
          % (asof, len(items), tot_sell, sum(i['onhand'] for i in items)))
    print(u'  在庫ゼロ %d SKU / 引当中 %d足'
          % (sum(1 for i in items if i['sellable'] == 0),
             sum(i['reserved'] for i in items)))
    low = [i for i in items if i['weeks'] is not None and i['weeks'] < 2]
    dead = [i for i in items if i['sellable'] > 0 and i['sold_recent'] == 0]
    print(u'  2週間以内に切れる %d SKU / 直近%d週で動いていない在庫 %d SKU(%d足)'
          % (len(low), WEEKS, len(dead), sum(i['sellable'] for i in dead)))
    if unmatched:
        print(u'  !! 販売実績にあるが在庫表に無い SKU: %s' % ', '.join(unmatched))


if __name__ == '__main__':
    main()
