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

書式が外れたセルは日付が Excel のシリアル値(`46261.5090` など)で降ってくるため、
`fix_date()` で文字列に戻している。

環境変数 `ORDERS_XLSX` でも指定できる(複数は `;` 区切り)。

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

### 商品マスタを足す

新しい SKU プレフィックスは `aggregate.py` の `MODEL` に、カラー略号は `COLORNAME` に追加する。
未登録の SKU は「その他」に落ちるだけで、集計自体は壊れない。

## 集計の定義

- **売上実績** — `order_status` が Completed または Shipped、かつ `payment_status` が Paid の注文。
  金額は注文合計(`total` = 商品合計 + 送料 − 値引き)
- **オフライン(店舗)** — `marketplace` = Barefoot Malaysia POS
- **オンライン** — Shopee / Lazada / 自社直販(`marketplace` 空欄)
- **失注** — Cancelled または Returned。売上には含めず別台帳で全件追跡
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
