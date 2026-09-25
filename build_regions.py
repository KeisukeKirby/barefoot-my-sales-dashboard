# -*- coding: utf-8 -*-
"""突合結果(region_map.json)から、公開して差し支えない regions.json を書き出す。

region_map.json は Drive の "Sales record for Malaysia.xlsx" を突き合わせた作業ファイルで、
顧客名・住所・電話を含むため **リポジトリには入れない**(.gitignore 済み)。
ここで order_id と地域だけを抜き出す。

  python reconcile_regions.py   # 突合 → region_map.json(作業用・PIIあり)
  python build_regions.py       # region_map.json → regions.json(公開用)
"""
import io, json, os, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get('SHEET_WORKDIR', HERE)
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(WORK, 'region_map.json')
OUT = os.path.join(HERE, 'regions.json')

# シートの From 欄 -> 表示グループ。右は英語表示。
GROUP = {
    'SG': ('シンガポール', 'Singapore'),
    'Singapore': ('シンガポール', 'Singapore'),
    'JB': ('ジョホール(地元)', 'Johor (local)'),
    'Johor': ('ジョホール(地元)', 'Johor (local)'),
    'KL': ('クアラルンプール', 'Kuala Lumpur'),
    'Selangor': ('セランゴール', 'Selangor'),
    'Penang': ('その他マレーシア', 'Other Malaysia'),
    'Negeri Sembilan': ('その他マレーシア', 'Other Malaysia'),
    'Perak': ('その他マレーシア', 'Other Malaysia'),
    'Kedah': ('その他マレーシア', 'Other Malaysia'),
    'EU': ('その他海外', 'Other overseas'),
    'London': ('その他海外', 'Other overseas'),
    'Local': ('不明', 'Unknown'),          # 「地元」の意味か判然としないため不明扱い
    '': ('不明', 'Unknown'),
}

# 地名としてそのまま出してよい値
PLACES = {'SG', 'Singapore', 'JB', 'Johor', 'KL', 'Selangor', 'Penang',
          'Negeri Sembilan', 'Perak', 'Kedah', 'EU', 'London'}

# From 欄には地名の代わりに従業員・親族の名前が入っている行がある。
# 名前をこの public なリポジトリに書かないため、判定に使う文字列は
# regions_staff.txt(1行1件・.gitignore 済み)に逃がしている。
# このファイルが無いと該当行は「不明」に落ちる(実行時に警告を出す)。
try:
    STAFF = [x.strip().lower() for x in
             io.open(os.path.join(HERE, 'regions_staff.txt'), encoding='utf-8')
             if x.strip() and not x.startswith('#')]
except (IOError, OSError):
    STAFF = []

ORDER = ['シンガポール', 'ジョホール(地元)', 'クアラルンプール', 'セランゴール',
         'その他マレーシア', 'その他海外', '関係者', '不明']


def main():
    src = json.load(io.open(SRC, encoding='utf-8'))
    out, unknown = {}, set()
    for oid, v in src.items():
        raw = (v.get('frm') or '').strip()
        if raw not in GROUP:
            unknown.add(raw)
        if raw in GROUP:
            grp, en = GROUP[raw]
        elif any(h in raw.lower() for h in STAFF):
            grp, en = '関係者', 'Staff / family'
            unknown.discard(raw)
        else:
            grp, en = '不明', 'Unknown'
        # シートの From には従業員・親族の個人名が入っている行があるので、
        # 公開するのは地名だけにする。それ以外はグループ名に落とす。
        out[oid] = dict(grp=grp, en=en, src='%s#%s' % (v['sheet'], v['no']))
        if raw in PLACES:
            out[oid]['raw'] = raw
    unknown = {u for u in unknown if not any(h in u.lower() for h in STAFF)}
    if unknown:
        print('!! GROUP に無い From の値(不明扱い):', sorted(unknown))
    if not STAFF:
        print('!! regions_staff.txt が無いので、従業員・親族の行も「不明」になっています')
    json.dump(dict(meta=dict(source='Sales record for Malaysia.xlsx (Google Drive)',
                             built=datetime.date.today().isoformat(),
                             note='シートの From 欄(来店客の自己申告)。国籍ではない',
                             order=ORDER),
                   regions=out),
              io.open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('regions.json written:', len(out), '注文')


if __name__ == '__main__':
    main()
