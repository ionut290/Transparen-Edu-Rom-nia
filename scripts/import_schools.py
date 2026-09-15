import io,json,re,unicodedata,urllib.request,time
from datetime import date
from openpyxl import load_workbook
from pypdf import PdfReader

DATASET='retea-scolara-2025-2026'
API=f'https://data.gov.ro/api/3/action/package_show?id={DATASET}'
NATIONAL_SOURCE=f'https://data.gov.ro/dataset/{DATASET}'
CURRENT_YEAR='2026-2027';LEGACY_YEAR='2025-2026'
HEADERS={'User-Agent':'Mozilla/5.0 TransparentaEduRomania/1.5','Accept':'*/*'}
COUNTY_SOURCES=[
 {'county':'SB','name':'Inspectoratul Școlar Județean Sibiu','page':'https://sbisj.ro/despre-noi/retea-scolara/','url':'https://docs.google.com/spreadsheets/d/1wwlcVOQJ-H70lx8oV3Kdthb07HLEUlTy/export?format=xlsx','format':'xlsx','schoolYear':LEGACY_YEAR},
 {'county':'TM','name':'Inspectoratul Școlar Județean Timiș','page':'https://www.isj.tm.edu.ro/retea-scolara','url':'https://www.isj.tm.edu.ro/public/data_files/media/2026/202603251518-Retea%20scolara%20pentru%20site%202026-2027.pdf','format':'pdf','schoolYear':CURRENT_YEAR},
]
OFFICIAL_NETWORK_PAGES=[{'county':s['county'],'name':s['name'],'page':s['page'],'schoolYear':s['schoolYear']} for s in COUNTY_SOURCES]

def download(url,timeout=90,attempts=3):
    last=None
    for attempt in range(1,attempts+1):
        try:
            print(f'Download {attempt}/{attempts}: {url}')
            req=urllib.request.Request(url,headers=HEADERS)
            with urllib.request.urlopen(req,timeout=timeout) as r:data=r.read()
            if not data:raise RuntimeError('Răspuns gol')
            return data
        except Exception as exc:
            last=exc;print(f'Încercarea {attempt} a eșuat: {exc}')
            if attempt<attempts:time.sleep(5*attempt)
    raise RuntimeError(f'Download eșuat: {last}')

def norm(v):
    s='' if v is None else str(v).strip();s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()

def pick(headers,*terms):
    for i,h in enumerate(headers):
        n=norm(h)
        if any(t in n for t in terms):return i
    return None

def val(row,i):
    if i is None or i>=len(row) or row[i] is None:return None
    return str(row[i]).strip()

def find_header_row(ws):
    for n,row in enumerate(ws.iter_rows(values_only=True),1):
        joined=' | '.join(norm(v) for v in row)
        if ('denumire' in joined or 'nume unit' in joined) and ('judet' in joined or 'localitate' in joined):return n,list(row)
    raise RuntimeError('Antetul rețelei școlare nu a fost găsit.')

def parse_xlsx(raw,source_url,forced_county=None,school_year=LEGACY_YEAR):
    if raw[:2]!=b'PK':raise RuntimeError('Fișierul nu este XLSX valid.')
    wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True);ws=wb[wb.sheetnames[0]];header_row,headers=find_header_row(ws)
    name_i=pick(headers,'denumire lunga unitate','denumire unitate','denumire','nume unit');county_i=pick(headers,'judet');locality_i=pick(headers,'localitate unitate','localitate')
    street_i=pick(headers,'strada','adresa');number_i=pick(headers,'numar');type_i=pick(headers,'categorie unitate','tip unitate','tipul unit');medium_i=pick(headers,'mediu loc unitate','mediu')
    code_i=pick(headers,'cod sirues','siiir','sirues','cod unit');status_i=pick(headers,'statut unitate','statut','status');parent_i=pick(headers,'denumire pj');schools=[]
    for row in ws.iter_rows(min_row=header_row+1,values_only=True):
        name=val(row,name_i)
        if not name:continue
        county=val(row,county_i) or forced_county;locality=val(row,locality_i);code=val(row,code_i);street=val(row,street_i);number=val(row,number_i)
        sid=code or 'ro-'+re.sub(r'[^a-z0-9]+','-',norm(f'{county}-{locality}-{name}')).strip('-')[:120]
        schools.append({'id':sid,'sirues':code,'name':name,'county':county,'locality':locality,'address':' '.join(x for x in [street,number] if x) or None,'type':val(row,type_i),'medium':val(row,medium_i),'status':val(row,status_i) or 'official','parentSchool':val(row,parent_i),'schoolYear':school_year,'sourceUrl':source_url})
    return schools

def parse_timisoara_pdf(raw,source_url):
    reader=PdfReader(io.BytesIO(raw))
    text='\n'.join((page.extract_text(extraction_mode='layout') or '') for page in reader.pages)
    if not text.strip():raise RuntimeError('PDF Timiș nu conține text extractibil.')
    schools=[]
    blocks=re.split(r'(?m)(?=^\s*\d+\s+2026-2027\s+TM\s+)',text)
    for block in blocks:
        m=re.match(r'^\s*(\d+)\s+2026-2027\s+TM\s+(.*)',block,re.S)
        if not m:continue
        lines=[re.sub(r'\s+',' ',x).strip() for x in block.splitlines() if x.strip()]
        joined=' '.join(lines)
        sm=re.search(r'\bUnitate de învățământ\s+(PJ|AR)\b',joined,re.I)
        if not sm:continue
        left=joined[:sm.start()].strip();status=sm.group(1).upper();left=re.sub(r'^\d+\s+2026-2027\s+TM\s+','',left)
        if len(left)<4:continue
        schools.append({'id':'tm-2026-'+m.group(1),'sirues':None,'name':left,'county':'TM','locality':None,'address':None,'type':None,'medium':None,'status':status,'parentSchool':None,'schoolYear':CURRENT_YEAR,'sourceUrl':source_url,'sourceRow':int(m.group(1))})
    if len(schools)<100:raise RuntimeError(f'PDF Timiș parsare suspectă: doar {len(schools)} rânduri')
    return schools

def parse_source(src):
    raw=download(src['url'],timeout=120,attempts=3)
    if src['format']=='xlsx':return parse_xlsx(raw,src['page'],src['county'],src['schoolYear'])
    if src['format']=='pdf' and src['county']=='TM':return parse_timisoara_pdf(raw,src['page'])
    raise RuntimeError('Format de sursă neacceptat')

def dedupe(items):
    by_key={}
    for s in items:
        key=s.get('sirues') or f"{s.get('schoolYear')}|{norm(s.get('county'))}|{norm(s.get('locality'))}|{norm(s.get('name'))}"
        old=by_key.get(key)
        if old is None or (s.get('schoolYear') or '')>(old.get('schoolYear') or ''):by_key[key]=s
    return list(by_key.values())

schools=[];sources=[];mode='county-first'
for src in COUNTY_SOURCES:
    try:
        part=parse_source(src);schools.extend(part);sources.append({'county':src['county'],'name':src['name'],'url':src['page'],'schoolYear':src['schoolYear'],'format':src['format'],'count':len(part)})
        print(f"{src['county']} {src['schoolYear']}: {len(part)} unități importate")
    except Exception as exc:print(f"{src['county']} a eșuat: {exc}")
try:
    meta=json.loads(download(API,timeout=25,attempts=1).decode('utf-8'))['result'];xlsx=next((r for r in meta.get('resources',[]) if str(r.get('format','')).lower()=='xlsx'),None)
    if not xlsx:raise RuntimeError('Resursa XLSX națională lipsește.')
    national=parse_xlsx(download(xlsx['url'],timeout=90,attempts=2),NATIONAL_SOURCE,school_year=LEGACY_YEAR);schools.extend(national)
    sources.append({'name':'Ministerul Educației / data.gov.ro','url':NATIONAL_SOURCE,'schoolYear':LEGACY_YEAR,'format':'xlsx','count':len(national)});mode='county-plus-national'
except Exception as exc:print(f'Fallback național indisponibil: {exc}')
schools=dedupe(schools)
if not schools:raise SystemExit('Nu s-a putut importa nicio unitate din sursele oficiale.')
current_count=sum(1 for s in schools if s.get('schoolYear')==CURRENT_YEAR);counties=sorted(set(s.get('county') for s in schools if s.get('county')))
coverage='national-current' if current_count>=1000 and len(counties)>=42 else ('mixed' if len(counties)>1 else 'partial')
schools.sort(key=lambda x:(x.get('county') or '',x.get('locality') or '',x.get('name') or ''))
out={'schemaVersion':6,'updatedAt':date.today().isoformat(),'targetSchoolYear':CURRENT_YEAR,'coverage':coverage,'importMode':mode,'count':len(schools),'currentYearCount':current_count,'counties':counties,'officialNetworkPages':OFFICIAL_NETWORK_PAGES,'sources':sources,'schools':schools}
with open('data/schools.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
print(f'Import finalizat: {len(schools)} unități; {current_count} pentru {CURRENT_YEAR}; județe={len(counties)}; acoperire={coverage}.')