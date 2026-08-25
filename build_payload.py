# -*- coding: utf-8 -*-
import sys, io, json, collections, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
J = json.load(open('agg.json', encoding='utf-8'))
O = [o for o in J['orders'] if o['bucket'] != 'test']
sales = [o for o in O if o['bucket'] == 'sales']
canc = [o for o in O if o['bucket'] == 'cancelled']
retn = [o for o in O if o['bucket'] == 'returned']
lost = canc + retn
unpaid = [o for o in O if o['pay'] == 'Unpaid']
R2 = lambda x: round(x + 1e-9, 2)
JOIN = ' / '


def items_str(o, skip_fee=False):
    out = []
    for i in o['items']:
        if skip_fee and i['cat'] == 'fee':
            continue
        s = i['size'] or ''
        out.append((i['model'] + ' ' + s).strip())
    return JOIN.join(out)


def block(gs):
    return dict(orders=len(gs), rev=R2(sum(o['total'] for o in gs)), units=sum(o['units'] for o in gs))


def isoff(o):
    return o['seg'].startswith(u'オフライン')  # オフライン


d0 = datetime.date(*map(int, min(o['date'] for o in O).split('-')))
d1 = datetime.date(*map(int, max(o['date'] for o in O).split('-')))
days = (d1 - d0).days + 1
alldates = [(d0 + datetime.timedelta(n)).isoformat() for n in range(days)]

dsale = collections.defaultdict(lambda: dict(off=0.0, on=0.0, o_off=0, o_on=0, units=0))
for o in sales:
    k = dsale[o['date']]
    if isoff(o):
        k['off'] += o['total']; k['o_off'] += 1
    else:
        k['on'] += o['total']; k['o_on'] += 1
    k['units'] += o['units']
dlost = collections.Counter()
for o in lost:
    dlost[o['date']] += o['total']
dline = collections.Counter()
dinv = collections.Counter()
dlostn = collections.Counter()
for o in sales:
    dline[o['date']] += o['n_lines']
    if o['invoice'].strip():
        dinv[o['date']] += 1
for o in lost:
    dlostn[o['date']] += 1
daily = [dict(date=d, off=R2(dsale[d]['off']), on=R2(dsale[d]['on']),
              orders=dsale[d]['o_off'] + dsale[d]['o_on'],
              off_orders=dsale[d]['o_off'], on_orders=dsale[d]['o_on'],
              units=dsale[d]['units'], lines=dline.get(d, 0), invoices=dinv.get(d, 0),
              lost=R2(dlost.get(d, 0)), lostn=dlostn.get(d, 0)) for d in alldates]


# --- 期間定義: 開業週は 7/17(金)〜7/26(日)、以降は月曜起点の週次 ---------------
WEEKS = [
    (u'W1', u'開業週', '2026-07-17', '2026-07-26'),
    (u'W2', u'第2週',  '2026-07-27', '2026-08-02'),
    (u'W3', u'第3週',  '2026-08-03', '2026-08-09'),
    (u'W4', u'第4週',  '2026-08-10', '2026-08-16'),
    (u'W5', u'第5週',  '2026-08-17', '2026-08-23'),
]
MONTHS = [
    (u'2026-07', u'2026年7月', '2026-07-17', '2026-07-31', u'開業月(7/17〜)'),
    (u'2026-08', u'2026年8月', '2026-08-01', '2026-08-31', u'進行中'),
]
LAST = d1.isoformat()


# --- 店舗の休業日 -------------------------------------------------------------
# 開業直後(7/17〜7/26)は連日営業。7/27・7/28 が最初の休業で、8月以降は毎週月・火。
WEEKLY_CLOSED_FROM = datetime.date(2026, 8, 1)
EXTRA_CLOSED = {datetime.date(2026, 7, 27), datetime.date(2026, 7, 28)}


def is_closed(d):
    if d in EXTRA_CLOSED:
        return True
    if d >= WEEKLY_CLOSED_FROM:
        return d.weekday() in (0, 1)      # 月・火
    return False


closed_days = [(d0 + datetime.timedelta(n)).isoformat()
               for n in range(days) if is_closed(d0 + datetime.timedelta(n))]


def invnum(o):
    try:
        return int(o['invoice'].split('-')[1])
    except (IndexError, ValueError):
        return None


def period_stats(a, b):
    s = [o for o in sales if a <= o['date'] <= b]
    l = [o for o in lost if a <= o['date'] <= b]
    u = [o for o in unpaid if a <= o['date'] <= b]
    so = [o for o in s if isoff(o)]
    sn = [o for o in s if not isoff(o)]
    nums = [n for n in (invnum(o) for o in s) if n is not None]
    da = datetime.date(*map(int, a.split('-')))
    db = datetime.date(*map(int, b.split('-')))
    dbe = min(db, d1)
    span = (db - da).days + 1
    elapsed = max(0, (dbe - da).days + 1)
    act = len(set(o['date'] for o in s))
    biz = sum(1 for n in range((dbe - da).days + 1)
              if not is_closed(da + datetime.timedelta(n))) if dbe >= da else 0
    return dict(
        start=a, end=b, span=span, elapsed=elapsed, ongoing=(db > d1),
        off=R2(sum(o['total'] for o in so)), on=R2(sum(o['total'] for o in sn)),
        rev=R2(sum(o['total'] for o in s)), orders=len(s), units=sum(o['units'] for o in s),
        off_orders=len(so), on_orders=len(sn),
        invoices=len(nums),                       # 伝票が発行された注文数
        no_invoice=len(s) - len(nums),            # 伝票番号なし(マーケットプレイス経由)
        inv_from=('INV-%d' % min(nums)) if nums else '—',
        inv_to=('INV-%d' % max(nums)) if nums else '—',
        lines=sum(o['n_lines'] for o in s),       # 明細行数
        unit_price=R2(sum(o['total'] for o in s) / sum(o['units'] for o in s)) if sum(o['units'] for o in s) else 0,
        aov=R2(sum(o['total'] for o in s) / len(s)) if s else 0,
        per_day=R2(sum(o['total'] for o in s) / elapsed) if elapsed else 0,
        biz_days=biz,                              # 経過分の店舗営業日数
        per_biz_day=R2(sum(o['total'] for o in s) / biz) if biz else 0,
        off_per_biz_day=R2(sum(o['total'] for o in so) / biz) if biz else 0,
        active_days=act,
        lost=R2(sum(o['total'] for o in l)), lostn=len(l),
        unpaid=R2(sum(o['total'] for o in u)), unpaidn=len(u))


weekly = [dict(id=i, label=lb, **period_stats(a, b)) for i, lb, a, b in WEEKS]
monthly = [dict(id=i, label=lb, note=nt, **period_stats(a, b)) for i, lb, a, b, nt in MONTHS]

CH_POS = u'POS(実店舗)'
CHORDER = [CH_POS, 'Shopee', 'Lazada', u'Online(直販)']


def channels_for(subset_sales, subset_lost):
    out = []
    for c in CHORDER:
        sc = [o for o in subset_sales if o['channel'] == c]
        lc = [o for o in subset_lost if o['channel'] == c]
        out.append(dict(name=c, seg=(u'オフライン' if c == CH_POS else u'オンライン'),
                        lost_orders=len(lc), lost_rev=R2(sum(o['total'] for o in lc)),
                        invoices=sum(1 for o in sc if o['invoice'].strip()),
                        lines=sum(o['n_lines'] for o in sc), **block(sc)))
    return out


chan = channels_for(sales, lost)
channels_by_month = {'all': chan}
for mid, lab, a, b, nt in MONTHS:
    channels_by_month[mid] = channels_for(
        [o for o in sales if a <= o['date'] <= b],
        [o for o in lost if a <= o['date'] <= b])


def models_for(subset):
    d = collections.defaultdict(lambda: dict(rev=0.0, units=0, brand='', off=0.0, on=0.0,
                                             off_units=0, on_units=0, prices=[]))
    for o in subset:
        for it in o['items']:
            if it['cat'] == 'test':
                continue
            m = d[it['model']]
            m['rev'] += it['total']
            m['units'] += it['qty']
            m['brand'] = it['brand']
            if isoff(o):
                m['off'] += it['total']
            else:
                m['on'] += it['total']
            if isoff(o):
                m['off_units'] += it['qty']
            else:
                m['on_units'] += it['qty']
            if it['qty'] > 0:
                m['prices'].append(it['price'])
    return [dict(name=k, brand=v['brand'], rev=R2(v['rev']), units=v['units'],
                 off=R2(v['off']), on=R2(v['on']),
                 off_units=v['off_units'], on_units=v['on_units'],
                 avg=R2(sum(v['prices']) / len(v['prices'])) if v['prices'] else 0)
            for k, v in sorted(d.items(), key=lambda x: -x[1]['rev'])]


models = models_for(sales)

# モデル別はプルダウンで月を切り替えるため、月ごとにも持たせる
models_by_month = {'all': models}
for mid, lab, a, b, nt in MONTHS:
    models_by_month[mid] = models_for([o for o in sales if a <= o['date'] <= b])

szW = collections.Counter(); szM = collections.Counter(); szO = collections.Counter()
for o in sales:
    for it in o['items']:
        if it['cat'] != 'shoes' or not it['size']:
            continue
        s = it['size']
        if s.startswith('W'):
            szW[s[1:]] += it['qty']
        elif s.startswith('M'):
            szM[s[1:]] += it['qty']
        else:
            szO[s] += it['qty']
def cmkey(k):
    try:
        return float(k.replace('cm', ''))
    except ValueError:
        return 999.0


sizes = dict(women=[dict(size=k, n=v) for k, v in sorted(szW.items())],
             men=[dict(size=k, n=v) for k, v in sorted(szM.items())],
             tabi=[dict(size=k, n=v) for k, v in sorted(szO.items(), key=lambda x: cmkey(x[0]))])

cc = collections.Counter()
for o in sales:
    for it in o['items']:
        if it['color']:
            cc[it['color']] += it['qty']
colors = [dict(name=k, n=v) for k, v in cc.most_common()]


def grp(gs, key):
    r = collections.defaultdict(lambda: dict(rev=0.0, orders=0, units=0))
    for o in gs:
        k = r[key(o)]
        k['rev'] += o['total']; k['orders'] += 1; k['units'] += o['units']
    return sorted([dict(name=n, rev=R2(v['rev']), orders=v['orders'], units=v['units'])
                   for n, v in r.items()], key=lambda x: -x['rev'])


states = grp(sales, lambda o: o['state'])
paym = grp(sales, lambda o: o['pay_method'])
WD = [u'月', u'火', u'水', u'木', u'金', u'土', u'日']
dow = [dict(name=WD[i], rev=0.0, orders=0, units=0) for i in range(7)]
for o in sales:
    i = datetime.date(*map(int, o['date'].split('-'))).weekday()
    dow[i]['rev'] = R2(dow[i]['rev'] + o['total'])
    dow[i]['orders'] += 1
    dow[i]['units'] += o['units']

hours = [dict(h=h, n=0, rev=0.0) for h in range(9, 22)]
hi = {h['h']: h for h in hours}
for o in sales:
    if not isoff(o):
        continue
    hh = int(o['dt'][11:13])
    if hh in hi:
        hi[hh]['n'] += 1
        hi[hh]['rev'] = R2(hi[hh]['rev'] + o['total'])

basket = collections.Counter(o['units'] for o in sales)

unpaid_rows = [dict(dt=o['dt'], invoice=o['invoice'], channel=o['channel'], status=o['status'],
                    total=R2(o['total']), units=o['units'], items=items_str(o))
               for o in sorted(unpaid, key=lambda x: x['dt'])]
lost_rows = [dict(dt=o['dt'], invoice=o['invoice'], channel=o['channel'], status=o['status'],
                  pay=o['pay'], total=R2(o['total']), units=o['units'], items=items_str(o))
             for o in sorted(lost, key=lambda x: x['dt'])]
sales_rows = [dict(dt=o['dt'], invoice=o['invoice'], channel=o['channel'], seg=o['seg'],
                   status=o['status'], total=R2(o['total']), units=o['units'], state=o['state'],
                   pay_method=o['pay_method'], items=items_str(o, skip_fee=True))
              for o in sorted(sales, key=lambda x: x['dt'])]

# 明細は1本にまとめ、画面側でプルダウン絞り込みする
KIND = {'sales': u'売上', 'cancelled': u'キャンセル', 'returned': u'返品'}
all_rows = [dict(dt=o['dt'], invoice=o['invoice'] or u'—', channel=o['channel'], seg=o['seg'],
                 status=o['status'], pay=o['pay'], kind=KIND.get(o['bucket'], o['bucket']),
                 bucket=o['bucket'], total=R2(o['total']), units=o['units'], state=o['state'],
                 lines=o['n_lines'], pay_method=o['pay_method'],
                 items=items_str(o, skip_fee=True))
            for o in sorted(O, key=lambda x: x['dt'])]

off = [o for o in sales if isoff(o)]
on = [o for o in sales if not isoff(o)]
loff = [o for o in lost if o['channel'] == CH_POS]
lon = [o for o in lost if o['channel'] != CH_POS]

P = dict(
    meta=dict(source=J['meta'].get('src') or J['meta'].get('source'),
              period=[d0.isoformat(), d1.isoformat()], days=days,
              lines=J['meta']['rows'], n_orders_raw=J['meta']['n_orders'], n_orders=len(O)),
    kpi=dict(total=block(sales), offline=block(off), online=block(on),
             lost=block(lost), cancelled=block(canc), returned=block(retn),
             unpaid=block(unpaid), lost_offline=block(loff), lost_online=block(lon),
             active_days=len([d for d in daily if d['off'] + d['on'] > 0])),
    daily=daily, weekly=weekly, monthly=monthly, closed_days=closed_days, channels=chan, channels_by_month=channels_by_month, models=models,
    models_by_month=models_by_month, sizes=sizes, colors=colors,
    states=states, payments=paym, dow=dow, hours=hours,
    basket=[dict(n=k, orders=v) for k, v in sorted(basket.items())],
    unpaid_rows=unpaid_rows, lost_rows=lost_rows, sales_rows=sales_rows, all_rows=all_rows,
)
open('payload.json', 'w', encoding='utf-8').write(json.dumps(P, ensure_ascii=False, separators=(',', ':')))
print('payload.json written', len(json.dumps(P, ensure_ascii=False)), 'chars')
print(json.dumps(P['kpi'], ensure_ascii=False, indent=1))
print('weekly:', json.dumps(P['weekly'], ensure_ascii=False, indent=1))
print('monthly:', json.dumps(P['monthly'], ensure_ascii=False, indent=1))
print('channels:', json.dumps(P['channels'], ensure_ascii=False, indent=1))
