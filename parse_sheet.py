# -*- coding: utf-8 -*-
"""Drive の "Sales record for Malaysia.xlsx" をテキスト化したもの(sheet_raw.txt)を
行に切り直して sheet.json を書く。

テキスト化の過程で「行の最終セル」と「次行の No.」が空白1つで連結されているため、
1行=15セルを前提に境界フィールドを割り直している。
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
    if b.endswith(TITLE):
        return '', b
    if b.isdigit():
        return '', b
    m = re.match(r'^(.*?)\s+(\d+)$', b)
    if m:
        return m.group(1), m.group(2)
    return b, ''


def money(s):
    s = (s or '').replace('RM', '').replace(',', '').strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def main():
    raw = io.open(os.path.join(HERE, 'sheet_raw.txt'), encoding='utf-8').read()
    F = [f.strip() for f in next(csv.reader([raw]))]
    R = (len(F) - 1) // 14
    assert 14 * R + 1 == len(F), (len(F), R)

    rows, carry = [], F[0]
    for k in range(R):
        mid = F[14 * k + 1: 14 * k + 14]
        if k + 1 < R:
            last, nxt = split_boundary(F[14 * (k + 1)], F[14 * (k + 1) + 1])
        else:
            last, nxt = F[-1], ''
        rows.append(dict(zip(COLS, [carry] + mid + [last])))
        carry = nxt

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
    for s in ('July2026', 'Aug2026', 'Sep2026'):
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
