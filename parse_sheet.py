# -*- coding: utf-8 -*-
"""Drive の "Sales record for Malaysia.xlsx" をテキスト化したもの(sheet_raw.txt)を
行に切り直して sheet.json を書く。

テキスト化の過程で「行の最終セル」と「次行の No.」が空白1つで連結されているため、
列数を前提に境界フィールドを割り直している。

列数はシートごとに違う。Nov2026 から備考列が1本増えて 16 列になったので、
見出し行の空セル数からシートごとに数える。COLS は先頭15列だけ使い、
16列目以降(備考)は落とす。
"""
import csv, io, json, os, re

HERE = os.environ.get('SHEET_WORKDIR', os.path.dirname(os.path.abspath(__file__)))
COLS = ['no', 'date', 'ch', 'cust', 'frm', 'pay', 'addr', 'prod', 'price',
        'walkin', 'online', 'courier', 'track', 'contact', 'last']
TITLE = 'Johor Bahru Sale record 2026'


def split_boundary(b, nx2):
    if nx2 == 'Date':
        return b[:-3].strip(), 'No.'
    if nx2 == 'TOTAL':
        return b, ''
    m = re.search(r'(\S+ ' + TITLE + r')$', b)   # 前の行の末尾 + 次のシートの見出し
    if m:
        return b[:m.start()].strip(), m.group(1)
    if b.endswith(TITLE):
        return '', b
    if b.isdigit():
        return '', b
    m = re.match(r'^(.*?)\s+(\d+)$', b)
    if m:
        return m.group(1), m.group(2)
    return b, ''


def sheet_strides(F):
    """[(見出しの位置, そのシートの列数)]。見出し行の後ろに並んでいる
    空セルを数える。その次に来るのはヘッダ行の 'No.' が境界で混じったフィールド。"""
    out = []
    for i, f in enumerate(F):
        if f.endswith(TITLE):
            j = i + 1
            while j < len(F) and F[j] == '':
                j += 1
            out.append((i, (j - i - 1) + 2))
    return out


def money(s):
    s = (s or '').replace('RM', '').replace(',', '').strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def main():
    raw = io.open(os.path.join(HERE, 'sheet_raw.txt'), encoding='utf-8').read()
    F = [f.strip() for f in next(csv.reader([raw]))]
    strides = sheet_strides(F)
    assert strides and strides[0][0] == 0, strides

    def mkrow(vals):
        # 16列目以降(備考)は捨てる。足りない分は空で埋める
        vals = (list(vals) + [''] * len(COLS))[:len(COLS)]
        return dict(zip(COLS, vals))

    rows, carry, i, si = [], F[0], 0, 0
    while i + 1 < len(F):
        while si + 1 < len(strides) and i >= strides[si + 1][0]:
            si += 1
        step = strides[si][1] - 1          # 1行あたりのフィールド数
        end = i + step
        if end >= len(F) - 1:
            # 最終行。次の行がないので境界の割り直しはしない
            rows.append(mkrow([carry] + F[i + 1:]))
            break
        last, nxt = split_boundary(F[end], F[end + 1])
        rows.append(mkrow([carry] + F[i + 1: end] + [last]))
        carry = nxt
        i = end
    R = len(rows)

    out, sheet, tot = [], None, {}
    for d in rows:
        if d['no'].endswith(TITLE):
            sheet = d['no'].split()[0]
            continue
        if d['no'] == 'No.':
            continue
        if d['date'] == 'TOTAL':
            tot[sheet] = (money(d['ch']), money(d['walkin']), money(d['online']))
            continue
        if not any(v for k, v in d.items() if k != 'no'):
            continue
        d['sheet'] = sheet
        out.append(d)

    json.dump(out, io.open(os.path.join(HERE, 'sheet.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('rows=%d  data=%d' % (R, len(out)))
    seen = []
    for x in out:                       # シートは出てきた順に出す
        if x['sheet'] not in seen:
            seen.append(x['sheet'])
    for s in seen:
        n = [x for x in out if x['sheet'] == s]
        w = round(sum(money(x['walkin']) or 0 for x in n), 2)
        o = round(sum(money(x['online']) or 0 for x in n), 2)
        p = round(sum(money(x['price']) or 0 for x in n), 2)
        t = tot[s]
        print('%-9s rows=%3d  walkin %10.2f (sheet %10.2f)  online %9.2f (sheet %9.2f)  price %10.2f (sheet total %10.2f)'
              % (s, len(n), w, t[1], o, t[2], p, t[0]))
    return out


if __name__ == '__main__':
    main()
