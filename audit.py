# -*- coding: utf-8 -*-
"""payload.json の各集計が、全注文を取りこぼしていないか検算する。

build_payload.py のあとに実行する。ズレがあれば内容を出して exit 1。

  python audit.py [payload.json]
"""
import io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(io.open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'payload.json'),
                      encoding='utf-8'))
A = json.load(io.open(os.path.join(HERE, 'agg.json'), encoding='utf-8'))['orders']
A = [o for o in A if o['bucket'] != 'test']
SALES = [o for o in A if o['bucket'] == 'sales']

K = P['kpi']['total']
NET, ORD, UNITS = K['rev'], K['orders'], K['units']
ng = []


def chk(name, got, want, unit=''):
    ok = abs(got - want) < 0.01 if isinstance(want, float) else got == want
    fmt = (lambda v: '{:,.2f}'.format(v)) if isinstance(want, float) else (lambda v: str(v))
    print('  %-40s %14s  (期待 %14s)  %s'
          % (name, fmt(got), fmt(want), 'OK' if ok else '<<< ズレ'))
    if not ok:
        ng.append((name, got, want, unit))


print('=== 基準: 売上 %d注文 / RM %.2f / %d足 ===' % (ORD, NET, UNITS))

print('\n[期間の集計]')
chk('日次 売上合計', round(sum(d['off'] + d['on'] + d['wh'] for d in P['daily']), 2), NET)
chk('日次 注文数', sum(d['orders'] for d in P['daily']), ORD)
chk('日次 点数', sum(d['units'] for d in P['daily']), UNITS)
chk('週別 売上合計', round(sum(w['rev'] for w in P['weekly']), 2), NET)
chk('週別 注文数', sum(w['orders'] for w in P['weekly']), ORD)
chk('週別 点数', sum(w['units'] for w in P['weekly']), UNITS)
chk('月別 売上合計', round(sum(m['rev'] for m in P['monthly']), 2), NET)
chk('月別 注文数', sum(m['orders'] for m in P['monthly']), ORD)
chk('月別 点数', sum(m['units'] for m in P['monthly']), UNITS)

print('\n[区分]')
chk('店舗+オンライン+卸売 売上',
    round(P['kpi']['offline']['rev'] + P['kpi']['online']['rev'] + P['kpi']['wholesale']['rev'], 2), NET)
chk('店舗+オンライン+卸売 注文数',
    P['kpi']['offline']['orders'] + P['kpi']['online']['orders'] + P['kpi']['wholesale']['orders'], ORD)
chk('チャネル別 売上合計', round(sum(c['rev'] for c in P['channels']), 2), NET)
chk('チャネル別 注文数', sum(c['orders'] for c in P['channels']), ORD)
for mid, rows in sorted(P['channels_by_month'].items()):
    if mid == 'all':
        continue
    m = [x for x in P['monthly'] if x['id'] == mid][0]
    chk('チャネル別(%s) 売上' % mid, round(sum(c['rev'] for c in rows), 2), m['rev'])

print('\n[切り口]')
chk('曜日別 売上合計', round(sum(d['rev'] for d in P['dow']), 2), NET)
chk('曜日別 注文数', sum(d['orders'] for d in P['dow']), ORD)
chk('決済方法 売上合計', round(sum(g['rev'] for g in P['payments']), 2), NET)
chk('決済方法 注文数', sum(g['orders'] for g in P['payments']), ORD)
chk('決済方法 内訳の合計', round(sum(i['rev'] for g in P['payments'] for i in g['items']), 2), NET)
chk('地域別 売上合計', round(sum(r['rev'] for r in P['regions']), 2), NET)
chk('地域別 注文数', sum(r['orders'] for r in P['regions']), ORD)
chk('州別 売上合計', round(sum(s['rev'] for s in P['states']), 2), NET)
chk('州別 注文数', sum(s['orders'] for s in P['states']), ORD)
chk('バスケット 注文数', sum(b['orders'] for b in P['basket']), ORD)
chk('店舗の時間帯別 注文数', sum(h['n'] for h in P['hours']), P['kpi']['offline']['orders'])
chk('店舗の時間帯別 売上', round(sum(h['rev'] for h in P['hours']), 2), P['kpi']['offline']['rev'])

print('\n[商品]')
mu = sum(m['units'] for m in P['models'])
chk('モデル別 数量合計', mu, UNITS)
chk('モデル別 店舗+ｵﾝﾗｲﾝ+卸売 数量',
    sum(m['off_units'] + m['on_units'] + m['wh_units'] for m in P['models']), mu)
chk('モデル別 店舗+ｵﾝﾗｲﾝ+卸売 売上',
    round(sum(m['off'] + m['on'] + m['wh'] for m in P['models']), 2),
    round(sum(m['rev'] for m in P['models']), 2))
for mid, rows in sorted(P['models_by_month'].items()):
    if mid == 'all':
        continue
    chk('モデル別(%s) 数量' % mid,
        sum(m['units'] for m in rows),
        sum(1 for _ in ()) or sum(o['units'] for o in SALES
                                  if [x for x in P['monthly'] if x['id'] == mid][0]['start'] <= o['date']
                                  <= [x for x in P['monthly'] if x['id'] == mid][0]['end']))
shoes = sum(o['shoe_units'] for o in SALES)
sz = sum(x['n'] for x in P['sizes']['women']) + sum(x['n'] for x in P['sizes']['men']) \
     + sum(x['n'] for x in P['sizes']['tabi'])
chk('サイズ別 合計(靴のみ)', sz, shoes)
chk('カラー別 合計', sum(c['n'] for c in P['colors']), UNITS)

print('\n[明細]')
chk('注文明細(すべて) 行数', len(P['all_rows']), len(A))
chk('売上明細 行数', len(P['sales_rows']), ORD)
chk('失注明細 行数', len(P['lost_rows']),
    P['kpi']['cancelled']['orders'] + P['kpi']['returned']['orders'])
chk('未入金明細 行数', len(P['unpaid_rows']), P['kpi']['unpaid']['orders'])
chk('注文明細 売上行の金額', round(sum(r['total'] for r in P['all_rows'] if r['bucket'] == 'sales'), 2), NET)

print('\n[元データとの突合]')
chk('agg.json の売上注文数', len(SALES), ORD)
chk('agg.json の売上金額', round(sum(o['total'] for o in SALES), 2), NET)
chk('agg.json の点数', sum(o['units'] for o in SALES), UNITS)

if ng:
    print('\n!!! %d 件ズレています' % len(ng))
    for n, g, w, _ in ng:
        print('   %-42s %s / 期待 %s' % (n, g, w))
    sys.exit(1)
print('\nすべて一致しました。')
