# Barefoot Malaysia 販売実績ダッシュボード

Barefoot Inc Malaysia(Johor Bahru 店舗 / Shopee / Lazada / 自社直販)の販売実績を
1枚の静的 HTML にまとめたダッシュボード。ビルド成果物は `index.html` 単体で、
外部ライブラリ・CDN・API に一切依存しない。

初回データ: 2026-07-17(開業日)〜 2026-08-21

## 中身

| ファイル | 役割 |
|---|---|
| `index.html` | **ビルド成果物**。これ単体で動く。Vercel が配信するのもこれ |
| `dashboard.html` | テンプレート(HTML / CSS / チャート描画)。`__PAYLOAD__` にデータが差し込まれる |
| `payload.json` | 集計済みデータ。テンプレートに埋め込まれる |
| `xlsxread.py` | xlsx リーダー(zipfile + xml の標準ライブラリのみ。pandas 不要) |
| `aggregate.py` | 明細行の読み込み・商品分類・注文単位への集約 → `agg.json` |
| `build_payload.py` | 期間定義に沿った集計 → `payload.json` |
| `parse_sheet.py` / `reconcile_regions.py` / `build_regions.py` | 販売記録シートとの突合 → `regions.json` |
| `build.py` | テンプレート + payload → `index.html` |

チャートは手書きの inline SVG。ビルドに Node も npm も不要で、必要なのは Python 3 だけ。

## 更新のしかた

管理画面から Orders をエクスポートした xlsx を用意して、上から順に実行する。

```bash
python aggregate.py "<Orders.xlsx>" ["<追加のOrders.xlsx>" ...] && python build_payload.py && python build.py
```

**エクスポートは差分で出てくることがある。** 2026-08-28 のエクスポートは INV-71 以降だけを
含んでいた。過去分のファイルもあわせて渡すこと。`aggregate.py` が `order_id` で統合し、
同じ注文が複数ファイルにあれば後ろのファイルを採用する。

**元の xlsx は移動・削除されることがある**(9/14 分は Downloads から消え、ごみ箱から取り出した)。
`aggregate.py` は実行のたびに統合済みの生データを `raw_orders.json` に保存するので、次回からは
過去分の xlsx の代わりにこれを先頭に渡せばよい。

```bash
python aggregate.py raw_orders.json "<新しいOrders.xlsx>" && python build_payload.py && python build.py
```

`raw_orders.json` は顧客名・電話・住所を含む。`.gitignore` 済みで、リポジトリは public なので
絶対にコミットしないこと。

書式が外れたセルは日付が Excel のシリアル値(`46261.5090` など)で降ってくるため、
`fix_date()` で文字列に戻している。起点は Excel 標準の **1899-12-30**。
order_id 103-110 の10行を実データと突き合わせて日時とも一致を確認済み(2026-08-31)。
起点を1日ずらすと日付が全て翌日になるので、変えないこと。

同じ注文が複数ファイルに入っていても `order_id` で1件に寄せるため、同じファイルを
何度渡しても二重計上にはならない。

環境変数 `ORDERS_XLSX` でも指定できる(複数は `;` 区切り)。

`build_payload.py` は卸売を含む `payload.json` と、卸売を除いた `payload_retail.json` の2つを
書き出す(後者は同じスクリプトを `EXCLUDE_WH=1` で自動的に再実行して作る)。画面の各セクションの
見出し下にある「卸売を除く」チェックは、そのセクションだけ後者のデータで描き直す。チェック状態は
ブラウザ(localStorage)に保存される。客単価はチェックに関係なく常に卸売を除いた値。

`index.html` を commit して push すれば Vercel が自動で再デプロイする。

### 期間の区切りを変える

`build_payload.py` の `WEEKS` / `MONTHS` を編集する。開業週だけ 7/17(金)〜7/26(日) の
10日間で、以降は月曜起点の週次。週を足すときは `WEEKS` に1行追加するだけ。

```python
WEEKS = [
    ('W1', '開業週', '2026-07-17', '2026-07-26'),
    ('W2', '第2週',  '2026-07-27', '2026-08-02'),
    ...
]
```

### エクスポートに載らない注文を足す

order_id 134 / 161 のように、どのエクスポートにも現れない注文がある。管理画面の注文詳細から
`aggregate.py` の `MANUAL_ORDERS` に書き起こす。明細が複数ある注文は `lines=[_ml(...), ...]` で書く。
161 は画面に明細単価が出ていなかったため注文合計を点数で均等割りしており、モデル別の金額だけは推定値。後日エクスポートに現れたらそちらが優先
される(手動分は `order_id` が未登録のときだけ取り込む)ので、消さずに残しておいてよい。

### 購入者の地域(販売記録スプレッドシートとの突合)

SiteGiant には購入者の地域が無いので、Google Drive の
`Sales record for Malaysia.xlsx`(店舗側が手でつけている台帳)の **From 欄** を
日付・チャネル・金額・商品・時刻で突き合わせて注文に紐づけている。

```bash
# 1. シートの中身を sheet_raw.txt に落とす(Drive から取得)
# 2. 行に切り直す → sheet.json
SHEET_WORKDIR=<作業フォルダ> python parse_sheet.py
# 3. 取込データと突合 → region_map.json、未結合の一覧を標準出力へ
SHEET_WORKDIR=<作業フォルダ> python reconcile_regions.py
# 4. 公開用に order_id と地域だけ抜き出す → regions.json
SHEET_WORKDIR=<作業フォルダ> python build_regions.py
```

`sheet_raw.txt` / `sheet.json` / `region_map.json` / `unmatched.json` は顧客名・住所・電話を
含むので `.gitignore` 済み。リポジトリに入れるのは `regions.json`(order_id と地域のみ。
従業員・親族の名前は「関係者」にまとめて落とす)だけ。

突合は自動でつかないものだけ `reconcile_regions.py` の `MANUAL` に理由付きで書く。
マーケットプレイスはシートが手取り額、SiteGiant が注文合計なので金額が数%ずれる。
同額の注文が同じ日に並ぶと取り違えるため、モデルとサイズも点数に入れている。

**地域は国籍ではない。** From 欄は店頭で聞き取った自己申告で、国籍の列はシートに無い。

### 商品マスタを足す

新しい SKU プレフィックスは `aggregate.py` の `MODEL` に、カラー略号は `COLORNAME` に追加する。
未登録の SKU は「その他」に落ちるだけで、集計自体は壊れない。

## 集計の定義

- **売上実績** — `payment_status` が Paid で、`order_status` が Completed / Shipped または出荷前
  (Pending Process / Processed / Ready To Ship)の注文。
  金額は注文合計(`total` = 商品合計 + 送料 − 値引き)
- **オフライン(店舗)** — `marketplace` = Barefoot Malaysia POS
- **オンライン** — Shopee / Lazada / 自社直販(`marketplace` 空欄)
- **卸売** — システム上の区分が無いため `aggregate.py` の `WHOLESALE` に注文IDを列挙する。
  法人名(`billing_company`)が入っていて未指定の注文があると集計時に警告が出るので、
  卸売ならIDを追加する。1件で通常の15倍の金額が動くため、混ぜると客単価も点数も歪む
- **失注** — Cancelled または Returned。売上には含めず別台帳で全件追跡
- **処理中** — `Pending Process` / `Processed` / `Ready To Ship`。入金済み(Paid)なら売上に数える
  (2026-09-14 オーナー判断)。未入金のものだけが「処理中」に残り、注文明細の「処理中のみ」で確認する。
  以前は Completed/Shipped/Returned 以外を全部キャンセルと判定していて、order 133 がキャンセル扱い
  になっていた。知らないステータスが来たら集計時に警告が出る
- **客単価 / 卸単価** — 客単価は卸売を除いた店舗+オンラインの売上 ÷ 注文数。卸売は1件で桁が違い
  平均を歪めるため、卸売の売上 ÷ 点数を卸単価として別に出す
- **未入金** — `payment_status` = Unpaid。売上にもキャッシュにも計上しない
- **点数** — シューズ・ソックスの数量合計。送料などのサービス行は除外し、返品行(数量 −1)は差し引く
- **モデル別売上** — 商品行(`product_total`)ベース。注文単位の値引き・送料を含まないため純売上とは一致しない
- **除外** — テスト注文(商品名 `test3` / `test4`)は全集計から除外

`product_cost` が元データでほぼ未入力のため、**粗利は算出していない**。

## API 連携(保留中)

xlsx の手動エクスポートをやめて注文を直接取得するため、SiteGiant Open API を調査した。
**Administrator 権限の承認が必要なため 2026-08-24 時点では保留。** 再開時のために調査結果を残す。

- ベースURL — `https://opensgapi.sitegiant.co/api/v1`
- 認証 — `Access-Token` ヘッダ
- ルート(疎通確認で判明) — `GET /orders`、`GET /orders/list`、`POST /order`、`PUT /order/list`
- Webhook — 注文イベントを HTTP POST で受信可(HMAC署名、3回リトライ、要 HTTPS)

**認証情報は2系統ある。混同しないこと。**

| 入口 | 認証情報 | 用途 |
|---|---|---|
| 店舗管理画面 Settings → API | Secret Key + Store Email | AutoCount / Biztory など会計ソフト連携 |
| opensgapi.sitegiant.co(開発者アカウント) | Access-Token | Open API |

店舗側の Secret Key で Open API を叩くと全ルートが `403 "Access denied due to invalid token"` を返す。
開発者アカウントの登録(`/register`)と、店舗の Administrator による承認が要る。

再開するときは `.env` に `SITEGIANT_TOKEN=<Access-Token>` を入れて疎通確認する。

```bash
python fetch_orders.py --probe
```

`GET /orders` が `200` を返したら、レスポンス形状に合わせて `aggregate.py` を繋ぎ込む。
`fetch_orders.py` はページングとパラメータ名の差し替えに対応済み。

## 注意

このダッシュボードは注文単位の売上明細を含む。リポジトリとデプロイ先の公開設定は
社内で共有できる範囲に合わせて設定すること。

`.env` は `.gitignore` 済みでコミットされない。トークン類をコードに直書きしないこと。
