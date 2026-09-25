# -*- coding: utf-8 -*-
"""Sales record スプレッドシート(Drive)と SiteGiant 取込データを突き合わせる。

金額だけだと同額の注文が同日に並んだときに取り違える(Trailope M44 と M46 など)ので、
日付・チャネル・金額・商品(モデル+サイズ)・時刻に点数をつけ、点数の高いペアから
貪欲に確定させる。オンラインはシートが手取り額、SiteGiant が注文合計なので金額がずれる。

出力: region_map.json / unmatched.json / 標準出力のレポート
"""
import io, json, os, re, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get('SHEET_WORKDIR', HERE)   # sheet.json など PII を含む作業ファイルの置き場
PROJ = HERE
START = '2026-07-17'
MON = dict(Jan=1, Feb=2, Mar=3, Apr=4, May=5, Jun=6,
           Jul=7, Aug=8, Sep=9, Oct=10, Nov=11, Dec=12)

CHMAP = {
    'walkin': 'POS(実店舗)', 'walk in': 'POS(実店舗)', 'pop up guest': 'POS(実店舗)',
    'shopee': 'Shopee', 'lazada': 'Lazada',
    'ig': 'Online(直販)', 'fb': 'Online(直販)', 'whatsapp': 'Online(直販)',
    'ws': 'Online(直販)', 'webstore': 'Online(直販)',
    'wholesale': '卸売', 'xnocs': '卸売',
}
# シートの略記 -> 取込データのモデル名
MODEL_KEY = [
    ('groundsplay', 'Groundsplay LS'), ('spidrwalk', 'Spidrwalk'), ('breezandal', 'Breezandal'),
    ('trailope', 'Trailope'), ('kso evo', 'KSO EVO'), ('v-alpha', 'V-Alpha'),
    ('v-soul', 'V-Soul'), ('v-run', 'V-Run'), ('vrun', 'V-Run'),
    ('tabirela', 'tabiRela'), ('tabi rela', 'tabiRela'), ('hitoe', 'Hitoe+'),
    ('bfj', 'Barefootinc.Jp Socks'), ('oln', 'Oleno'), ('oleno', 'Oleno'),
    ('ultimate', 'Oleno'), ('aso', 'Oleno'),
]

# 自動では結びつかなかった行の手当て。理由を必ず残す。
MANUAL = {
    # (sheet, no): (order_id, 理由)
    ('Aug2026', '54'): ('136', 'XNOCS 卸売 RM11,701.62。金額が完全一致。SiteGiant の計上日は 9/2、シートは 8/27'),
    ('Sep2026', '24'): ('161', '卸売 RM17,339.40。金額が完全一致。SiteGiant の計上日は 9/2、シートは 9/11'),
    ('Aug2026', '14'): ('57',  'V-Run M41 + KSO EVO M41 と品目・時刻(11:20 / 11:45)が一致。'
                               'シートの RM1,046 は RM1,406 の数字入れ替えとみられる'),
    ('Aug2026', '34'): ('78',  'tabiRela 24.5 + 25 と時刻 16:06 が一致。金額はシート RM390 / POS RM65 で不一致(値引きの記録差)'),
    ('July2026', '18'): ('20', 'V-Soul W38 + 配送料 RM562、日付も一致。WS(SNS経由)の注文を店頭POSで起票したため'
                               'チャネルが食い違う'),
    ('July2026', '12'): ('13', 'V-Run M42 + Oleno ASO の RM773.50 を SiteGiant では oid 13(RM680)と '
                               'oid 14(RM93.50)の2注文に分けて起票。地域は両方に当てる'),
}
MANUAL_EXTRA = {('July2026', '12'): '14'}   # 1行が2注文に分かれるケース


def sheet_date(s):
    s = (s or '').strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return s[:10]
    m = re.match(r'^(\d{1,2})([A-Za-z]{3})[a-z]*(\d{4})$', s)
    if m and m.group(2).capitalize() in MON:
        return '%s-%02d-%02d' % (m.group(3), MON[m.group(2).capitalize()], int(m.group(1)))
    return None


def money(s):
    s = (s or '').replace('RM', '').replace(',', '').strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def hhmm(s):
    m = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', s or '', re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), (m.group(3) or '').lower()
    if ap == 'pm' and h < 12:
        h += 12
    if ap == 'am' and h == 12:
        h = 0
    return h * 60 + mi


def sheet_tokens(txt):
    """シートの品名欄からモデル名とサイズを拾う。"""
    t = (txt or '').lower()
    models = {full for key, full in MODEL_KEY if key in t}
    sizes = set()
    for m in re.finditer(r'\b(?:eu\s*)?([mw])\s*(\d{2})\b', t):
        sizes.add(m.group(1).upper() + m.group(2))
    for m in re.finditer(r'\beu\s*(\d{2})\b', t):
        sizes.add(m.group(1))
    for m in re.finditer(r'\b(\d{2}(?:\.\d)?)\s*(?:cm)?\b', t):   # 足袋の cm 表記
        sizes.add(m.group(1))
    return models, sizes


def order_tokens(o):
    models = {i['model'] for i in o['items'] if i['model']}
    sizes = set()
    for i in o['items']:
        if i['size']:
            s = str(i['size'])
            sizes.add(s.upper())
            sizes.add(re.sub(r'[^\d.]', '', s))
    return models, sizes


def omin(o):
    try:
        h, m = o['dt'][11:16].split(':')
        return int(h) * 60 + int(m)
    except Exception:
        return None


rows = json.load(io.open(os.path.join(WORK, 'sheet.json'), encoding='utf-8'))
orders = [o for o in json.load(io.open(os.path.join(PROJ, 'agg.json'), encoding='utf-8'))['orders']
          if o['bucket'] != 'test']
BY = {o['order_id']: o for o in orders}

for r in rows:
    d = sheet_date(r['date'])
    if d is None and r['sheet'] == 'July2026' and r['no'] == '18':
        d = '2026-07-21'           # 日付セルが #### で潰れている。Payment Details から復元
    r['d'] = d
    r['amts'] = [v for v in (money(r['walkin']), money(r['online']), money(r['price'])) if v]
    r['t'] = hhmm(r['pay'])
    r['ch_n'] = CHMAP.get((r['ch'] or '').strip().lower())
    r['mods'], r['sizes'] = sheet_tokens(r['prod'])

IN = [r for r in rows if r['d'] and r['d'] >= START]
OUTSIDE = [r for r in rows if not (r['d'] and r['d'] >= START)]


def score(r, o):
    """ペアの確からしさ。None なら候補にしない。"""
    dd = abs((datetime.date(*map(int, r['d'].split('-'))) -
              datetime.date(*map(int, o['date'].split('-')))).days)
    if dd > 3:
        return None
    amt = min((abs(o['total'] - a) / a if a else 9) for a in r['amts']) if r['amts'] else 9
    om, sm = order_tokens(o)
    # モデル名は表記ゆれがあるので部分一致で数える(Oleno / Oleno Ultimate など)
    mod = sum(1 for a in r['mods']
              if any(a.lower() in b.lower() or b.lower() in a.lower() for b in om))
    siz = len(r['sizes'] & sm)
    tm = abs(omin(o) - r['t']) if (omin(o) is not None and r['t'] is not None) else None

    s = 0
    if amt <= 0.0001: s += 6
    elif amt <= 0.08: s += 4          # マーケットプレイスの手数料ぶんのずれ
    elif amt <= 0.20: s += 1
    else: s -= 2
    s += (3, 1, 0, 0)[dd]
    s += 2 * siz + mod
    if r['ch_n'] == o['channel']: s += 3
    else: s -= 2                      # 店頭POSで起票したオンライン注文などがある
    if tm is not None:
        s += 3 if tm == 0 else (2 if tm <= 20 else (1 if tm <= 60 else 0))
    if o['bucket'] == 'sales': s += 1
    # 品名が読み取れるのに1つも重ならないものは、金額が完全一致でない限り採らない
    if r['mods'] and om and mod == 0 and amt > 0.0001: s -= 5
    return s


MIN = 6
pairs, used, cand = [], set(), []
for r in IN:
    for o in orders:
        sc = score(r, o)
        if sc is not None and sc >= MIN:
            cand.append((sc, r, o))
cand.sort(key=lambda x: -x[0])
for sc, r, o in cand:
    if r.get('_m') or o['order_id'] in used:
        continue
    r['_m'] = o['order_id']
    used.add(o['order_id'])
    pairs.append((r, o, sc, '自動(score %d)' % sc))

# 手当て
for r in IN:
    key = (r['sheet'], r['no'])
    if key in MANUAL:
        oid, why = MANUAL[key]
        if r.get('_m') and r['_m'] != oid:
            print('!! 手当てと自動突合が衝突: %s #%s (自動 %s / 手当て %s)' % (r['sheet'], r['no'], r['_m'], oid))
            continue
        if not r.get('_m'):
            r['_m'] = oid
            used.add(oid)
            pairs.append((r, BY[oid], None, '手当て: ' + why))
        if key in MANUAL_EXTRA:
            used.add(MANUAL_EXTRA[key])
            pairs.append((r, BY[MANUAL_EXTRA[key]], None, '手当て(2注文に分割): ' + why))

REG = {}
for r, o, sc, how in pairs:
    REG[o['order_id']] = dict(frm=r['frm'], sheet=r['sheet'], no=r['no'], how=how,
                              ch=r['ch'], cust=r['cust'], prod=r['prod'],
                              sheet_amt=r['amts'][0] if r['amts'] else None,
                              order_amt=o['total'], sheet_date=r['d'], order_date=o['date'])
json.dump(REG, io.open(os.path.join(WORK, 'region_map.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

un_sheet = [r for r in IN if not r.get('_m')]
un_ord = sorted([o for o in orders if o['order_id'] not in used],
                key=lambda x: (x['date'], int(x['order_id'])))
json.dump(dict(sheet=[{k: r[k] for k in ('sheet', 'no', 'd', 'ch', 'frm', 'prod', 'amts')} for r in un_sheet],
               orders=[dict(oid=o['order_id'], dt=o['dt'], bucket=o['bucket'], ch=o['channel'],
                            inv=o['invoice'], total=o['total'],
                            items=' / '.join('%s %s' % (i['model'], i['size'] or '') for i in o['items']))
                       for o in un_ord]),
          io.open(os.path.join(WORK, 'unmatched.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print('=== 突合サマリー ===')
print('シート 全%d行 / 7/17以降 %d行 / 対象外(開業前・日付欠落) %d行' % (len(rows), len(IN), len(OUTSIDE)))
print('取込データ %d注文(テスト2件除く)' % len(orders))
print('結びついた注文 %d  |  シート側の未結合 %d行  |  注文側の未結合 %d件'
      % (len(REG), len(un_sheet), len(un_ord)))

print('\n=== シート側で結びつかなかった行(%d) ===' % len(un_sheet))
for r in un_sheet:
    print('  %-4s#%-3s %s %-13s %-18s %-34s %s'
          % (r['sheet'][:3], r['no'], r['d'], r['ch'], (r['frm'] or '(空欄)')[:18],
             (r['prod'] or '(品名なし)')[:34], r['amts']))

print('\n=== 取込データ側で結びつかなかった注文(%d) ===' % len(un_ord))
for o in un_ord:
    print('  oid %-4s %s %-9s %-11s %-8s RM %9.2f  %s'
          % (o['order_id'], o['dt'], o['bucket'], o['channel'], o['invoice'] or '-', o['total'],
             ' / '.join('%s %s' % (i['model'], i['size'] or '') for i in o['items'])[:42]))

print('\n=== From(地域)分布 ===')
cnt, rev = {}, {}
for oid, v in REG.items():
    k = v['frm'] or '(空欄)'
    cnt[k] = cnt.get(k, 0) + 1
    if BY[oid]['bucket'] == 'sales':
        rev[k] = rev.get(k, 0) + BY[oid]['total']
for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
    print('  %-24s %3d注文  売上 RM %9.2f' % (k, v, rev.get(k, 0)))
