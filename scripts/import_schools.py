import io,json,re,unicodedata,urllib.request,time
from datetime import date
from openpyxl import load_workbook

DATASET='retea-scolara-2025-2026'
API=f'https://data.gov.ro/api/3/action/package_show?id={DATASET}'
NATIONAL_SOURCE=f'https://data.gov.ro/dataset/{DATASET}'
HEADERS={'User-Agent':'Mozilla/5.0 TransparentaEduRomania/1.2','Accept':'*/*'}
# Surse oficiale județene folosite când portalul național data.gov.ro nu răspunde.
# Lista poate fi extinsă progresiv cu cele 41 județe + București.
COUNTY_SOURCES=[
 {'county':'SB','name':'Inspectoratul Școlar Județean Sibiu','page':'https://sbisj.ro/despre-noi/retea-scolara/','url':'https://docs.google.com/spreadsheets/d/1wwlcVOQJ-H70lx8oV3Kdthb07HLEUlTy/export?format=xlsx'},
]

def download(url,timeout=90,attempts=3):
    last=None
    for attempt in range(1,attempts+1):
        try:
            print(f'Download {attempt}/{attempts}: {url}')
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=timeout) as r:data=r.read()
            if not data: raise RuntimeError('Răspuns gol')
            return data
        except Exception as exc:
            last=exc;print(f'Încercarea {attempt} a eșuat: {exc}')
            if attempt<attempts:time.sleep(5*attempt)
    raise RuntimeError(f'Download eșuat: {last}')

def norm(v):
    s='' if v is None else str(v).strip()
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def find_header_row(ws):
    for n,row in enumerate(ws.iter_rows(values_only=True),1):
        vals=[norm(v) for v in row]
        joined=' | '.join(vals)
        if ('denumire' in joined or 'nume unit' in joined) and ('judet' in joined or 'localitate' in joined):return n,list(row)
    raise RuntimeError('Antetul rețelei școlare nu a fost găsit.')

def pick(headers,*terms):
    for i,h in enumerate(headers):
        n=norm(h)
        if any(t in n for t in terms):return i
    return None

def val(row,i):
    if i is None or i>=len(row) or row[i] is None:return None
    return str(row[i]).strip()

def parse_xlsx(raw,source_url,forced_county=None):
    if raw[:2]!=b'PK':raise RuntimeError('Fișierul nu este XLSX valid.')
    wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    ws=wb[wb.sheetnames[0]]
    header_row,headers=find_header_row(ws)
    name_i=pick(headers,'denumire lunga unitate','denumire unitate','denumire','nume unit')
    county_i=pick(headers,'judet')
    locality_i=pick(headers,'localitate unitate','localitate')
    street_i=pick(headers,'strada','adresa')
    number_i=pick(headers,'numar')
    type_i=pick(headers,'categorie unitate','tip unitate','tipul unit')
    medium_i=pick(headers,'mediu loc unitate','mediu')
    code_i=pick(headers,'cod sirues','siiir','sirues','cod unit')
    status_i=pick(headers,'statut unitate','statut','status')
    parent_i=pick(headers,'denumire pj')
    schools=[]
    for row in ws.iter_rows(min_row=header_row+1,values_only=True):
        name=val(row,name_i)
        if not name:continue
        county=val(row,county_i) or forced_county
        locality=val(row,locality_i)
        code=val(row,code_i)
        street=val(row,street_i);number=val(row,number_i)
        address=' '.join(x for x in [street,number] if x) or None
        sid=code or 'ro-'+re.sub(r'[^a-z0-9]+','-',norm(f'{county}-{locality}-{name}')).strip('-')[:120]
        schools.append({'id':sid,'sirues':code,'name':name,'county':county,'locality':locality,'address':address,'type':val(row,type_i),'medium':val(row,medium_i),'status':val(row,status_i) or 'official','parentSchool':val(row,parent_i),'schoolYear':'2025-2026','sourceUrl':source_url})
    return schools

def dedupe(items):
    out=[];seen=set()
    for s in items:
        key=s.get('sirues') or f"{norm(s.get('county'))}|{norm(s.get('locality'))}|{norm(s.get('name'))}"
        if key in seen:continue
        seen.add(key);out.append(s)
    return out

schools=[];sources=[];mode='national'
try:
    meta=json.loads(download(API,timeout=45,attempts=2).decode('utf-8'))['result']
    xlsx=next((r for r in meta.get('resources',[]) if str(r.get('format','')).lower()=='xlsx'),None)
    if not xlsx:raise RuntimeError('Resursa XLSX națională lipsește.')
    schools=parse_xlsx(download(xlsx['url'],timeout=120,attempts=3),NATIONAL_SOURCE)
    sources.append({'name':'Ministerul Educației / data.gov.ro','url':NATIONAL_SOURCE,'count':len(schools)})
except Exception as exc:
    print(f'Sursa națională indisponibilă: {exc}')
    print('Trec pe sursele oficiale ale inspectoratelor școlare.')
    mode='county-fallback'
    for src in COUNTY_SOURCES:
        try:
            part=parse_xlsx(download(src['url'],timeout=120,attempts=3),src['page'],src['county'])
            schools.extend(part);sources.append({'county':src['county'],'name':src['name'],'url':src['page'],'count':len(part)})
            print(f"{src['county']}: {len(part)} unități importate")
        except Exception as exc2:print(f"{src['county']} a eșuat: {exc2}")

schools=dedupe(schools)
if not schools:raise SystemExit('Nu s-a putut importa nicio unitate din sursele oficiale.')
# Nu pretindem acoperire națională când rulează fallback-ul parțial.
coverage='national' if mode=='national' and len(schools)>=1000 else 'partial'
schools.sort(key=lambda x:(x.get('county') or '',x.get('locality') or '',x.get('name') or ''))
out={'schemaVersion':3,'updatedAt':date.today().isoformat(),'schoolYear':'2025-2026','coverage':coverage,'importMode':mode,'count':len(schools),'sources':sources,'schools':schools}
with open('data/schools.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
print(f'Import finalizat: {len(schools)} unități; acoperire={coverage}; mod={mode}.')