# -*- coding: utf-8 -*-
import os, sys, io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
import xlsxread, collections, json, re, datetime

DEFAULT_SRC = os.path.join(os.path.expanduser('~'), 'Downloads',
                           'Copy of Orders_21-08-2026-1787304991_1.xlsx')
SRCS = sys.argv[1:] or [x for x in os.environ.get('ORDERS_XLSX', DEFAULT_SRC).split(os.pathsep) if x]
missing = [x for x in SRCS if not os.path.exists(x)]
if missing:
    sys.exit(u'Orders の xlsx が見つかりません: ' + ', '.join(missing) +
             u'\n  使い方: python aggregate.py "<Orders.xlsx>" ["<追加のOrders.xlsx>" ...]')

# エクスポートは差分で出てくることがあるため、複数ファイルを order_id で統合する。
# 同じ order_id が複数ファイルにあれば後のファイル(新しい方)を採用。
# raw_orders.json(前回までに統合した生データ)もソースとして渡せる。元の xlsx が
# 移動・削除されても再集計できるようにするため(9/14 分の xlsx が実際に消えた)。
ARCHIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw_orders.json')


def read_source(path):
    if path.lower().endswith('.json'):
        arch = json.load(open(path, encoding='utf-8'))
        return arch['header'], arch['rows'], arch.get('sources', [])
    rows = xlsxread.read(path)
    h = rows[0]
    return (h, [dict(zip(h, r + [''] * (len(h) - len(r)))) for r in rows[1:]],
            [os.path.basename(path)])


merged, header, sources = {}, None, []
for path in SRCS:
    h, drows, srcnames = read_source(path)
    header = header or h
    sources += [x for x in srcnames if x not in sources]
    for d in drows:
        merged.setdefault(d['order_id'], {'src': path, 'lines': []})
        if merged[d['order_id']]['src'] != path:       # 別ファイルの同一注文は差し替え
            merged[d['order_id']] = {'src': path, 'lines': []}
        merged[d['order_id']]['lines'].append(d)

# 統合した生データを保存する。顧客名・住所を含むので .gitignore 済み。絶対にコミットしない。
# 手動補完分は含めない(エクスポート由来の行だけを次回のソースにする)。
json.dump({'header': header, 'sources': sources,
           'rows': [ln for k in sorted(merged, key=lambda x: int(x) if str(x).isdigit() else 0)
                    for ln in merged[k]['lines']]},
          open(ARCHIVE, 'w', encoding='utf-8'), ensure_ascii=False)

# --- エクスポートに載らなかった注文の手動補完 ---------------------------------
# order_id 134 は全エクスポートで欠番だった(133 → 135)。管理画面の注文詳細から
# 起こしている。後日エクスポートに現れたらそちらが優先される(下の取り込み条件)。
def _ml(sku, name, qty, unit='481.65'):
    """手動補完用の明細行。"""
    return dict(product_sku=sku, product_name='Vibram FiveFingers ' + name,
                product_price=unit, product_quantity=str(qty),
                product_total='%.2f' % (float(unit) * qty))


MANUAL_ORDERS = [
    dict(order_id='134', invoice_no='',                       # Lazada 経由は伝票番号なし
         order_creation_date='2026-08-31 11:07',
         order_status='Completed', payment_status='Paid',
         marketplace='Barefoot Malaysia - Lazada',
         product_sku='VFF0008(BR,W38)',                       # 色は 2026-09-25 にオーナーから brown と確認
         product_name='Vibram Fivefingers V-Soul Model, Pilates/Yoga Shoes '
                      'Training Shoes for Women-EU:38',
         product_price='650.00', product_quantity='1', product_total='650.00',
         total='650.00', billing_firstname='J*g'),

    # order_id 161 も全エクスポートで欠番(160 → 162)。管理画面の注文詳細から起こした卸売。
    # 画面に明細ごとの単価が出ていないため、注文合計を点数で均等割りしている
    # (RM 17,339.40 / 36点 = 481.65)。売上・点数・サイズは正確、モデル別の金額だけ推定値。
    # 色: 2026-09-25 にもらった注文詳細の画像でも商品名が途中で切れているため、
    # Spidrwalk は表記どおり Total Black、Breezandal はサムネイルと販売記録の色表記から
    # 男性 BK / 女性 IV/GR と判断した。Groundsplay LS のレディースだけは特定できず UNK。
    dict(order_id='161', invoice_no='',
         order_creation_date='2026-09-02 10:00',
         order_status='Shipped', payment_status='Paid', marketplace='',
         total='17339.40', billing_firstname='Hock Soon', billing_lastname='Ng',
         lines=[_ml('VFF0021(BK,M40)',  'Groundsplay LS Model for Men', 2),
                _ml('VFF0021(BK,M41)',  'Groundsplay LS Model for Men', 3),
                _ml('VFF0021(BK,M42)',  'Groundsplay LS Model for Men', 4),
                _ml('VFF0021(BK,M43)',  'Groundsplay LS Model for Men', 2),
                _ml('VFF0021(BK,M44)',  'Groundsplay LS Model for Men', 1),
                _ml('VFF0021(BK,M45)',  'Groundsplay LS Model for Men', 1),
                _ml('VFF0021(UNK,W37)', 'Groundsplay LS Model for Women', 1),
                _ml('VFF0021(UNK,W38)', 'Groundsplay LS Model for Women', 3),
                _ml('VFF0021(UNK,W39)', 'Groundsplay LS Model for Women', 2),
                _ml('VFF0026(TT/BK,M40)', "Spidrwalk Men's Water and Outdoor Shoes, Color Total Black-40", 2),
                _ml('VFF0026(TT/BK,M41)', "Spidrwalk Men's Water and Outdoor Shoes, Color Total Black-41", 2),
                _ml('VFF0026(TT/BK,M42)', "Spidrwalk Men's Water and Outdoor Shoes, Color Total Black-42", 2),
                _ml('VFF0026(TT/BK,M43)', "Spidrwalk Men's Water and Outdoor Shoes, Color Total Black-43", 1),
                _ml('VFF0022(BK,M40)',  'Breezandal Model for Men', 1),
                _ml('VFF0022(BK,M41)',  'Breezandal Model for Men', 2),
                _ml('VFF0022(BK,M42)',  'Breezandal Model for Men', 3),
                _ml('VFF0022(BK,M43)',  'Breezandal Model for Men', 1),
                _ml('VFF0022(BK,M44)',  'Breezandal Model for Men', 1),
                _ml('VFF0022(IV/GR,W38)', 'Breezandal Model for Women', 1),
                _ml('VFF0022(IV/GR,W39)', 'Breezandal Model for Women', 1)]),
]
_units_161 = sum(int(x['product_quantity']) for x in MANUAL_ORDERS[-1]['lines'])
_lines_161 = round(sum(float(x['product_total']) for x in MANUAL_ORDERS[-1]['lines']), 2)
assert _units_161 == 36 and _lines_161 == 17339.40, (_units_161, _lines_161)   # 画面の数字と一致させる

for mo in MANUAL_ORDERS:
    if mo['order_id'] in merged:                              # エクスポート優先
        continue
    common = {k: v for k, v in mo.items() if k != 'lines'}
    rows = []
    for ln in mo.get('lines', [{}]):                          # 明細が無ければ1行の注文
        row = {k: '' for k in (header or [])}
        row.update(common)
        row.update(ln)
        rows.append(row)
    merged[mo['order_id']] = {'src': '(manual)', 'lines': rows}

# 書式が外れたセルは日付が Excel のシリアル値で降ってくる。起点は Excel 標準の
# 1899-12-30。order_id 103-110 の10行を実データと突き合わせて日時とも一致を確認済み
# (2026-08-31)。当たった注文は警告に出し、書式付きで再エクスポートできるようにする。
EPOCH = datetime.datetime(1899, 12, 30)
serial_hits = []


def fix_date(v, oid=''):
    v = str(v).strip()
    if not v or '-' in v:
        return v
    try:
        d = EPOCH + datetime.timedelta(days=float(v))
    except ValueError:
        return v
    serial_hits.append(oid)
    return d.strftime('%Y-%m-%d %H:%M')


data = []
for oid in sorted(merged, key=lambda x: int(x) if str(x).isdigit() else 0):
    for d in merged[oid]['lines']:
        d['order_creation_date'] = fix_date(d['order_creation_date'], oid)
        data.append(d)

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
    ('VFF0021', 'Groundsplay LS', 'Vibram FiveFingers', 'shoes'),
    ('VFF0022', 'Breezandal', 'Vibram FiveFingers', 'shoes'),
    ('VFF0023', 'V-Alpha',    'Vibram FiveFingers', 'shoes'),
    ('VFF0024', 'Trailope',   'Vibram FiveFingers', 'shoes'),
    ('VFF0026', 'Spidrwalk',  'Vibram FiveFingers', 'shoes'),
    ('MTB0001', 'tabiRela',   'Marugo Tabi',        'shoes'),
    ('MTB0002', 'Hitoe+',     'Marugo Tabi',        'shoes'),
    ('Marugo Tab', 'tabiRela','Marugo Tabi',        'shoes'),
    ('BFJ0001', 'Barefootinc.Jp Socks', 'Socks',    'socks'),
    ('QLN0002', 'Oleno Ultimate',       'Socks',    'socks'),
]
COLORNAME = {'BK':'Black','BR':'Brown','BB/BL':'Baby Blue','BK/LI/BK':'Black-Lime','TT/BK':'Total Black',
             'LI/GN':'Lime Green','FU':'Fuchsia','DL/BK':'Deep Lake','DL':'Deep Lake',
             'ZB/WT':'Zebra White','LM':'Lemon','UNK':'(色不明)',
             'F/IV/GN':'Fig/Ivory/Green','TT/IV':'Total Ivory','GY':'Gray',
             'TK/M':'Tsuki/Moon','UM/O':'Umi/Ocean','IV/GR':'Ivory/Green'}

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

# 卸売はシステム上の区分が無く POS でも marketplace でもないため、注文IDで指定する。
# 1件で通常の15倍以上の金額が動くので、混ぜると客単価も点数も歪む。
# 136 / 161 はいずれも Hock Soon Ng(Yellowstone Sdn Bhd)宛、2026-09-02。
WHOLESALE = {'136', '161'}


def channel_of(d):
    if d['order_id'] in WHOLESALE:
        return '卸売'
    return CH.get(d['marketplace'], d['marketplace'] or 'Online(直販)')


def seg_of(ch):
    if ch == '卸売':
        return '卸売'
    return 'オフライン(店舗)' if ch == 'POS(実店舗)' else 'オンライン'

# ---- build line + order records --------------------------------------------
lines = []
for d in data:
    model, brand, cat, color, size = classify(d)
    lines.append(dict(
        order_id=d['order_id'], invoice=d['invoice_no'],
        dt=d['order_creation_date'], date=d['order_creation_date'][:10],
        status=d['order_status'], pay=d['payment_status'],
        channel=channel_of(d),
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
# 出荷前の途中ステータス。以前は「それ以外は全部キャンセル」で判定していたため、
# 支払い済みの注文がキャンセル扱いになっていた。Paid なら売上、未入金なら「処理中」に残す。
PENDING = ('Pending Process', 'Processed', 'Ready To Ship')
unknown_status = set()


def bucket(v):
    a = v[0]
    if is_test(v): return 'test'
    if a['status'] in ('Completed', 'Shipped') and a['pay'] == 'Paid': return 'sales'
    # 入金済みの出荷前注文も売上に数える(2026-09-14 オーナー判断)。後日のエクスポートで
    # キャンセルに変われば order_id 統合でそちらが優先される。
    if a['status'] in PENDING and a['pay'] == 'Paid': return 'sales'
    if a['status'] == 'Returned': return 'returned'
    if a['status'] == 'Cancelled': return 'cancelled'
    if a['status'] not in PENDING:
        unknown_status.add(a['status'])            # 見知らぬステータスは黙って丸めない
    return 'pending'

O = []
for oid, v in orders.items():
    a = v[0]
    O.append(dict(order_id=oid, invoice=a['invoice'], dt=a['dt'], date=a['date'],
                  status=a['status'], pay=a['pay'], channel=a['channel'], seg=seg_of(a['channel']),
                  pay_method=a['pay_method'], state=a['state'], city=a['city'],
                  customer=a['customer'], bucket=bucket(v),
                  total=a['order_total'], ship_fee=a['ship_fee'],
                  coupon=a['coupon'], adj=a['adj'],
                  gross=sum(L['line_total'] for L in v),
                  units=sum(L['qty'] for L in v if L['cat'] in ('shoes', 'socks')),
                  shoe_units=sum(L['qty'] for L in v if L['cat'] == 'shoes'),
                  vff_units=sum(L['qty'] for L in v
                                if L['cat'] == 'shoes' and L['brand'] == 'Vibram FiveFingers'),
                  n_lines=len(v),
                  items=[dict(sku=L['sku'], model=L['model'], brand=L['brand'], cat=L['cat'],
                              color=L['color'], size=L['size'], price=L['price'],
                              qty=L['qty'], total=L['line_total'], pname=L['pname']) for L in v]))
O.sort(key=lambda x: x['dt'])

sales = [o for o in O if o['bucket'] == 'sales']
canc  = [o for o in O if o['bucket'] == 'cancelled']
retn  = [o for o in O if o['bucket'] == 'returned']
test  = [o for o in O if o['bucket'] == 'test']
pend  = [o for o in O if o['bucket'] == 'pending']
unpaid = [o for o in O if o['pay'] == 'Unpaid']

out = dict(orders=O, meta=dict(
    src=' + '.join(sources),                       # アーカイブ経由でも元のファイル名を出す
    rows=len(data), n_orders=len(O),
    period=[min(o['date'] for o in O), max(o['date'] for o in O)],
))
json.dump(out, open('agg.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

company_orders = {}
for d in data:
    if d.get('billing_company', '').strip() and d['order_id'] not in WHOLESALE:
        company_orders[d['order_id']] = d['billing_company'].strip()
if company_orders:
    print()
    print('!' * 72)
    print(u'法人名が入っていて卸売に未指定の注文があります。卸売なら WHOLESALE に追加してください:')
    for k, v in sorted(company_orders.items(), key=lambda x: int(x[0])):
        print(u'  order_id %s  %s' % (k, v))
    print('!' * 72)

if unknown_status:
    print()
    print('!' * 72)
    print(u'知らない order_status があります(売上に入れず処理中として扱いました): ' + ', '.join(sorted(unknown_status)))
    print(u'売上に含めるべきステータスなら bucket() を見直してください。')
    print('!' * 72)

if serial_hits:
    ids = sorted(set(serial_hits), key=lambda x: int(x) if str(x).isdigit() else 0)
    print()
    print('!' * 72)
    print(u'日付が Excel のシリアル値で入っていた注文が %d 件あります: %s' % (len(ids), ', '.join(ids)))
    print(u'日付は復元しましたが時刻は当てになりません。該当分を再エクスポートして渡し直してください。')
    print('!' * 72)

R = lambda x: round(x, 2)
print('=== BUCKETS (orders / revenue RM / units) ===')
for nm, g in [('売上(Paid: 完了・出荷済・出荷前)', sales), ('キャンセル', canc), ('返品', retn), ('処理中(入金済・出荷前)', pend), ('テスト', test)]:
    print(f'{nm:32} {len(g):>3}件  RM {R(sum(o["total"] for o in g)):>10,.2f}  {sum(o["units"] for o in g):>3}足')
print(f'{"うちUnpaid(未入金)":32} {len(unpaid):>3}件  RM {R(sum(o["total"] for o in unpaid)):>10,.2f}  {sum(o["units"] for o in unpaid):>3}足')
print()
rev = sum(o['total'] for o in sales); un = sum(o['units'] for o in sales)
print(f'純売上 RM {rev:,.2f} / 注文 {len(sales)} / AOV RM {rev/len(sales):,.2f} / 販売数 {un} / 単価 RM {rev/un:,.2f}')
print(f'キャンセル率(件数) {len(canc)/(len(O)-len(test))*100:.1f}%  返品率 {len(retn)/(len(O)-len(test))*100:.1f}%')

# 未登録SKUは cat='other' に落ち、数量にカウントされない。黙って消えると
# 「点数が合わない」形でしか気づけないので、ここで必ず目に入るようにする。
unknown = {}
for o in O:
    for it in o['items']:
        if it['cat'] == 'other':
            unknown.setdefault(it['sku'] or '(SKUなし)', it['pname'])
if unknown:
    print()
    print('!' * 72)
    print(f'未登録のSKUが {len(unknown)} 件あります。数量に計上されていません。')
    print('aggregate.py の MODEL に追加してから再実行してください。')
    for sku, name in sorted(unknown.items()):
        print(f'  {sku:24} {name[:70]}')
    print('!' * 72)
