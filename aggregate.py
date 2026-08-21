# -*- coding: utf-8 -*-
import os, sys, io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import xlsxread, collections, json, re, datetime

DEFAULT_SRC = os.path.join(os.path.expanduser('~'), 'Downloads',
                           'Copy of Orders_21-08-2026-1787304991_1.xlsx')
SRC = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ORDERS_XLSX', DEFAULT_SRC)
if not os.path.exists(SRC):
    sys.exit(u'Orders の xlsx が見つかりません: ' + SRC +
             u'\n  使い方: python aggregate.py "<Orders.xlsx のパス>"')
rows = xlsxread.read(SRC)
h = rows[0]
data = [dict(zip(h, r + [''] * (len(h) - len(r)))) for r in rows[1:]]

def f(x):
    try: return float(str(x).strip() or 0)
    except: return 0.0
def i(x):
    try: return int(float(str(x).strip() or 0))
    except: return 0

# ---- product classification -------------------------------------------------
MODEL = [
    ('VFF0002', 'V-Run',      'Vibram FiveFingers', 'shoes'),
    ('VFF0008', 'V-Soul',     'Vibram FiveFingers', 'shoes'),
    ('VFF0009', 'KSO EVO',    'Vibram FiveFingers', 'shoes'),
    ('VFF0024', 'Trailope',   'Vibram FiveFingers', 'shoes'),
    ('VFF0026', 'Spidrwalk',  'Vibram FiveFingers', 'shoes'),
    ('MTB0002', 'Hitoe+',     'Marugo Tabi',        'shoes'),
    ('Marugo Tab', 'tabiRela','Marugo Tabi',        'shoes'),
    ('BFJ0001', 'Barefootinc.Jp Socks', 'Socks',    'socks'),
    ('QLN0002', 'Oleno Ultimate',       'Socks',    'socks'),
]
COLORNAME = {'BK':'Black','BR':'Brown','BB/BL':'Baby Blue','BK/LI/BK':'Black-Lime','TT/BK':'Total Black',
             'LI/GN':'Lime Green','FU':'Fuchsia','DL/BK':'Deep Lake','ZB/WT':'Zebra White'}

def classify(d):
    sku, name = d['product_sku'].strip(), d['product_name'].strip()
    if name in ('test3', 'test4'):        return ('TEST', 'TEST', 'test', None, None)
    if 'courier fee' in name.lower():     return ('配送料', 'その他', 'fee', None, None)
    for pre, model, brand, cat in MODEL:
        if sku.startswith(pre): break
    else:
        if 'Oleno' in name: return ('Oleno Ultimate', 'Socks', 'socks', None, None)
        return (name[:30] or '(不明)', 'その他', 'other', None, None)
    m = re.search(r'\(([^,]+),\s*([^)]+)\)', sku)
    color = size = None
    if m:
        color = COLORNAME.get(m.group(1), m.group(1))
        size = m.group(2)
    if brand == 'Marugo Tabi':
        # Marugo は cm 表記。SKU に寸法が無いものは商品名末尾から拾う
        cm = re.search(r'-\s*(\d+(?:\.\d+)?)\s*cm', name)
        if cm:
            size = cm.group(1) + 'cm'
        elif size and size.replace('.', '').isdigit():
            size = size + 'cm'
        if color is None:
            cn = re.search(r',\s*(?:Color\s+)?([^,\-]+?)\s*-\s*\d', name)
            if cn:
                color = cn.group(1).strip()
    return (model, brand, cat, color, size)

CH = {'Barefoot Malaysia POS': 'POS(実店舗)', 'Barefoot Malaysia - Shopee': 'Shopee',
      'Barefoot Malaysia - Lazada': 'Lazada', '': 'Online(直販)'}

# ---- build line + order records --------------------------------------------
lines = []
for d in data:
    model, brand, cat, color, size = classify(d)
    lines.append(dict(
        order_id=d['order_id'], invoice=d['invoice_no'],
        dt=d['order_creation_date'], date=d['order_creation_date'][:10],
        status=d['order_status'], pay=d['payment_status'],
        channel=CH.get(d['marketplace'], d['marketplace'] or 'Online(直販)'),
        pay_method=d['billing_method'], state=d['billing_state'] or '(不明)',
        city=d['billing_city'] or '(不明)',
        sku=d['product_sku'], pname=d['product_name'],
        model=model, brand=brand, cat=cat, color=color, size=size,
        price=f(d['product_price']), qty=i(d['product_quantity']),
        line_total=f(d['product_total']),
        order_total=f(d['total']), ship_fee=f(d['shipping_fee']),
        coupon=f(d['coupon_amount']), adj=f(d['other_adjustment_total']),
        customer=(d['billing_firstname'] + ' ' + d['billing_lastname']).strip(),
    ))

orders = collections.OrderedDict()
for L in lines:
    orders.setdefault(L['order_id'], []).append(L)

def is_test(v):  return all(L['cat'] == 'test' for L in v)
def bucket(v):
    a = v[0]
    if is_test(v): return 'test'
    if a['status'] in ('Completed', 'Shipped') and a['pay'] == 'Paid': return 'sales'
    if a['status'] == 'Returned': return 'returned'
    return 'cancelled'

O = []
for oid, v in orders.items():
    a = v[0]
    O.append(dict(order_id=oid, invoice=a['invoice'], dt=a['dt'], date=a['date'],
                  status=a['status'], pay=a['pay'], channel=a['channel'], seg=('オフライン(店舗)' if a['channel']=='POS(実店舗)' else 'オンライン'),
                  pay_method=a['pay_method'], state=a['state'], city=a['city'],
                  customer=a['customer'], bucket=bucket(v),
                  total=a['order_total'], ship_fee=a['ship_fee'],
                  coupon=a['coupon'], adj=a['adj'],
                  gross=sum(L['line_total'] for L in v),
                  units=sum(L['qty'] for L in v if L['cat'] in ('shoes', 'socks')),
                  n_lines=len(v),
                  items=[dict(sku=L['sku'], model=L['model'], brand=L['brand'], cat=L['cat'],
                              color=L['color'], size=L['size'], price=L['price'],
                              qty=L['qty'], total=L['line_total'], pname=L['pname']) for L in v]))
O.sort(key=lambda x: x['dt'])

sales = [o for o in O if o['bucket'] == 'sales']
canc  = [o for o in O if o['bucket'] == 'cancelled']
retn  = [o for o in O if o['bucket'] == 'returned']
test  = [o for o in O if o['bucket'] == 'test']
unpaid = [o for o in O if o['pay'] == 'Unpaid']

out = dict(orders=O, meta=dict(
    src=os.path.basename(SRC),
    rows=len(data), n_orders=len(O),
    period=[min(o['date'] for o in O), max(o['date'] for o in O)],
))
json.dump(out, open('agg.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

R = lambda x: round(x, 2)
print('=== BUCKETS (orders / revenue RM / units) ===')
for nm, g in [('売上(Completed+Shipped/Paid)', sales), ('キャンセル', canc), ('返品', retn), ('テスト', test)]:
    print(f'{nm:32} {len(g):>3}件  RM {R(sum(o["total"] for o in g)):>10,.2f}  {sum(o["units"] for o in g):>3}足')
print(f'{"うちUnpaid(未入金)":32} {len(unpaid):>3}件  RM {R(sum(o["total"] for o in unpaid)):>10,.2f}  {sum(o["units"] for o in unpaid):>3}足')
print()
rev = sum(o['total'] for o in sales); un = sum(o['units'] for o in sales)
print(f'純売上 RM {rev:,.2f} / 注文 {len(sales)} / AOV RM {rev/len(sales):,.2f} / 販売数 {un} / 単価 RM {rev/un:,.2f}')
print(f'キャンセル率(件数) {len(canc)/(len(O)-len(test))*100:.1f}%  返品率 {len(retn)/(len(O)-len(test))*100:.1f}%')
