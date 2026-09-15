import io,json,re,unicodedata,urllib.request
from datetime import date
from openpyxl import load_workbook

DATASET='retea-scolara-2025-2026'
API=f'https://data.gov.ro/api/3/action/package_show?id={DATASET}'
SOURCE=f'https://data.gov.ro/dataset/{DATASET}'

def norm(v):
    s='' if v is None else str(v).strip()
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def pick(headers,*terms):
    for i,h in enumerate(headers):
        n=norm(h)
        if any(t in n for t in terms): return i
    return None

def val(row,i):
    if i is None or i>=len(row) or row[i] is None:return None
    return str(row[i]).strip()

req=urllib.request.Request(API,headers={'User-Agent':'TransparentaEduRomania/1.0'})
with urllib.request.urlopen(req,timeout=60) as r: meta=json.load(r)['result']
resources=meta.get('resources',[])
xlsx=next((r for r in resources if str(r.get('format','')).lower()=='xlsx'),None)
if not xlsx: raise SystemExit('Nu am găsit resursa XLSX oficială.')
with urllib.request.urlopen(xlsx['url'],timeout=120) as r: raw=r.read()
wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
ws=wb[wb.sheetnames[0]]
rows=ws.iter_rows(values_only=True)
headers=list(next(rows))
name_i=pick(headers,'denumire','nume unit','unitate invatamant')
county_i=pick(headers,'judet')
locality_i=pick(headers,'localitate','localizare')
address_i=pick(headers,'adresa')
type_i=pick(headers,'tip unit','tipul unit','categorie')
medium_i=pick(headers,'mediu')
code_i=pick(headers,'siiir','sirues','cod unit','cod siiir')
status_i=pick(headers,'statut','status')
if name_i is None: raise SystemExit(f'Coloana denumire nu a fost găsită: {headers}')

schools=[]
seen=set()
for n,row in enumerate(rows,2):
    name=val(row,name_i)
    if not name: continue
    code=val(row,code_i)
    county=val(row,county_i)
    locality=val(row,locality_i)
    key=code or f'{norm(county)}|{norm(locality)}|{norm(name)}'
    if key in seen: continue
    seen.add(key)
    sid=code or 'ro-'+re.sub(r'[^a-z0-9]+','-',norm(f'{county}-{locality}-{name}')).strip('-')[:120]
    schools.append({
      'id':sid,'sirues':code,'name':name,'county':county,'locality':locality,
      'address':val(row,address_i),'type':val(row,type_i),'medium':val(row,medium_i),
      'status':val(row,status_i) or 'official','schoolYear':'2025-2026','sourceUrl':SOURCE
    })
schools.sort(key=lambda x:(x.get('county') or '',x.get('locality') or '',x.get('name') or ''))
out={'schemaVersion':2,'updatedAt':date.today().isoformat(),'schoolYear':'2025-2026','source':'Ministerul Educației – data.gov.ro, Rețeaua școlară 2025-2026','sourceUrl':SOURCE,'count':len(schools),'schools':schools}
with open('data/schools.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
print(f'Importate {len(schools)} unități.')