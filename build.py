# -*- coding: utf-8 -*-
"""dashboard.html(テンプレート)+ payload.json → index.html を生成する。

集計スクリプト(aggregate.py / build_payload.py)は scratchpad 側にあるため、
payload.json のパスは引数か PAYLOAD 環境変数で差し替えられるようにしている。
"""
import io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, 'dashboard.html')
OUT = os.path.join(HERE, 'index.html')
PAY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('PAYLOAD', os.path.join(HERE, 'payload.json'))

tpl = io.open(TPL, encoding='utf-8').read()
if '__PAYLOAD__' not in tpl:
    sys.exit('dashboard.html に __PAYLOAD__ プレースホルダがありません')
pay = io.open(PAY, encoding='utf-8').read()
io.open(OUT, 'w', encoding='utf-8').write(tpl.replace('__PAYLOAD__', pay))
print('built', OUT, len(tpl) + len(pay), 'chars  <-', PAY)
