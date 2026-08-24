# -*- coding: utf-8 -*-
"""SiteGiant Open API から注文を取得して orders.json に保存する。

トークンはコードに書かない。環境変数 SITEGIANT_TOKEN か、同じフォルダの .env
(gitignore 済み)から読む。.env の書き方:

    SITEGIANT_TOKEN=ここにトークン

使い方:
    python fetch_orders.py --probe              # 疎通確認。何が返るか見るだけ
    python fetch_orders.py --from 2026-07-17 --to 2026-08-31

エンドポイントのパスとパラメータ名は SiteGiant の Postman コレクションで
確定させる。まだ確定していないため --path / --params で差し替えられるようにしてある。
"""
import argparse, json, os, sys, urllib.error, urllib.parse, urllib.request

BASE = os.environ.get('SITEGIANT_BASE', 'https://opensgapi.sitegiant.co/api/v1')
HERE = os.path.dirname(os.path.abspath(__file__))


def load_token():
    tok = os.environ.get('SITEGIANT_TOKEN')
    if tok:
        return tok.strip()
    envf = os.path.join(HERE, '.env')
    if os.path.exists(envf):
        for line in open(envf, encoding='utf-8'):
            line = line.strip()
            if line.startswith('SITEGIANT_TOKEN='):
                return line.split('=', 1)[1].strip().strip('"\'')
    sys.exit('SITEGIANT_TOKEN が見つかりません。.env に SITEGIANT_TOKEN=... を書くか、'
             '環境変数に設定してください。')


def call(path, params, token, method='GET', body=None):
    url = BASE.rstrip('/') + '/' + path.lstrip('/')
    if params and method == 'GET':
        url += '?' + urllib.parse.urlencode(params)
    payload = None
    if method != 'GET':
        payload = json.dumps(body if body is not None else (params or {})).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method=method, headers={
        'Access-Token': token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode('utf-8', 'replace')
            return r.status, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8', 'replace')


def mask(text, token):
    """出力にトークンが混ざっても外に出さない。probe の結果を貼れるようにするため。"""
    return text.replace(token, '***TOKEN***') if token else text


def probe(token):
    """トークンでどのパスが通るか総当たりで確認する。"""
    print('base:', BASE)
    # 405 の応答が Supported methods を教えてくれるので、メソッドも総当たりする
    attempts = [
        ('GET', 'orders'), ('GET', 'orders/list'),
        ('POST', 'order'), ('PUT', 'order/list'), ('POST', 'order/list'),
        ('GET', 'me'), ('GET', 'shop'), ('GET', 'store'),
    ]
    for method, path in attempts:
        st, hdr, body = call(path, {'page': 1}, token, method=method)
        rl = hdr.get('X-RateLimit-Remaining', '-')
        print(f'  {method:5} /{path:12} -> {st}  rate={rl}  {mask(body[:200], token)!r}')


def fetch_all(path, token, extra, page_param, per_page_param, per_page):
    out, page = [], 1
    while True:
        params = dict(extra)
        params[page_param] = page
        if per_page_param:
            params[per_page_param] = per_page
        st, hdr, body = call(path, params, token)
        if st != 200:
            sys.exit(f'HTTP {st}: {body[:400]}')
        try:
            data = json.loads(body)
        except ValueError:
            sys.exit('JSON として読めない応答: ' + body[:400])
        # レスポンス形状は実物を見て確定させる。よくある形を順に探す。
        rows = None
        for k in ('data', 'orders', 'result', 'items'):
            v = data.get(k) if isinstance(data, dict) else None
            if isinstance(v, list):
                rows = v
                break
            if isinstance(v, dict):
                for k2 in ('data', 'orders', 'items'):
                    if isinstance(v.get(k2), list):
                        rows = v[k2]
                        break
            if rows is not None:
                break
        if rows is None and isinstance(data, list):
            rows = data
        if rows is None:
            print('注文配列の場所が判別できません。生の応答を raw_response.json に保存します。')
            json.dump(data, open(os.path.join(HERE, 'raw_response.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
            sys.exit(1)
        out.extend(rows)
        print(f'  page {page}: {len(rows)} 件 (累計 {len(out)})')
        if not rows:
            break
        page += 1
        if page > 200:
            print('ページ上限に達したので打ち切ります。')
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--probe', action='store_true', help='疎通確認のみ')
    ap.add_argument('--path', default='orders', help='注文一覧のパス')
    ap.add_argument('--from', dest='dfrom', help='開始日 YYYY-MM-DD')
    ap.add_argument('--to', dest='dto', help='終了日 YYYY-MM-DD')
    ap.add_argument('--from-param', default='date_from')
    ap.add_argument('--to-param', default='date_to')
    ap.add_argument('--page-param', default='page')
    ap.add_argument('--per-page-param', default='per_page')
    ap.add_argument('--per-page', type=int, default=100)
    ap.add_argument('--out', default=os.path.join(HERE, 'orders.json'))
    a = ap.parse_args()

    token = load_token()
    if a.probe:
        probe(token)
        return
    extra = {}
    if a.dfrom:
        extra[a.from_param] = a.dfrom
    if a.dto:
        extra[a.to_param] = a.dto
    rows = fetch_all(a.path, token, extra, a.page_param, a.per_page_param, a.per_page)
    json.dump(rows, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{len(rows)} 件を {a.out} に保存しました。')


if __name__ == '__main__':
    main()
