# -*- coding: utf-8 -*-
"""SKU の読み方。販売(aggregate.py)と在庫(build_stock.py)で同じ表を使う。
片方にだけモデルを追加して、もう片方で「未登録」になるのを防ぐため。
"""

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
    ('OLN0001', 'Oleno Ultimate',       'Socks',    'socks'),
    ('QLN0002', 'Oleno Ultimate Aso',   'Socks',    'socks'),   # 商品名は Ultimate Aso。型番も別
    ('OLN0003', 'Oleno Ultimate TNG',   'Socks',    'socks'),   # 2026-11-08 に初販売
    # ここから下は在庫にはあるがまだ売れていない(2026-11-15 時点)
    ('QLN0003', 'Oleno Ultimate TNG',   'Socks',    'socks'),   # Black/Blue の型番
    ('VFF0025', 'Scramkey',             'Vibram FiveFingers', 'shoes'),
]
COLORNAME = {'BK':'Black','BR':'Brown','BB/BL':'Baby Blue','BK/LI/BK':'Black-Lime','TT/BK':'Total Black',
             'LI/GN':'Lime Green','FU':'Fuchsia','DL/BK':'Deep Lake','DL':'Deep Lake',
             'ZB/WT':'Zebra White','LM':'Lemon','UNK':'(色不明)',
             'F/IV/GN':'Fig/Ivory/Green','TT/IV':'Total Ivory','GY':'Gray',
             'TK/M':'Tsuki/Moon','UM/O':'Umi/Ocean','IV/GR':'Ivory/Green',
             'IV/DL':'Ivory/Deep Lake','BK/GR':'Black/Gray',
             'BK/BL':'Black/Blue','ZB/NV':'Zebra Navy','DN':'Denim'}
