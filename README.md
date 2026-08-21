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
python aggregate.py "<Orders.xlsx のパス>" && python build_payload.py && python build.py
```

引数を省略すると `~/Downloads/Copy of Orders_21-08-2026-1787304991_1.xlsx` を読む。
環境変数 `ORDERS_XLSX` でも指定できる。

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

## 注意

このダッシュボードは注文単位の売上明細を含む。リポジトリとデプロイ先の公開設定は
社内で共有できる範囲に合わせて設定すること。
