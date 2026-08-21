import zipfile, re, datetime
from xml.etree import ElementTree as ET
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

def col_idx(ref):
    m=re.match(r'([A-Z]+)', ref); c=0
    for ch in m.group(1): c=c*26+(ord(ch)-64)
    return c-1

def read(path, sheet='xl/worksheets/sheet1.xml'):
    z=zipfile.ZipFile(path)
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        r=ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in r.findall(NS+'si'):
            shared.append(''.join(t.text or '' for t in si.iter(NS+'t')))
    root=ET.fromstring(z.read(sheet))
    rows=[]
    for row in root.iter(NS+'row'):
        cells={}
        for c in row.findall(NS+'c'):
            ref=c.get('r'); t=c.get('t'); i=col_idx(ref)
            v=c.find(NS+'v'); isel=c.find(NS+'is')
            if t=='s' and v is not None: val=shared[int(v.text)]
            elif t=='inlineStr' and isel is not None: val=''.join(x.text or '' for x in isel.iter(NS+'t'))
            elif v is not None: val=v.text
            else: val=''
            cells[i]=val
        n=(max(cells)+1) if cells else 0
        rows.append([cells.get(i,'') for i in range(n)])
    return rows
