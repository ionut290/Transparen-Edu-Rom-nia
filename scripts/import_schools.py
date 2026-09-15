import io,json,re,unicodedata,urllib.request,time
from datetime import date
from openpyxl import load_workbook
from pypdf import PdfReader

DATASET='retea-scolara-2025-2026'; API=f'https://data.gov.ro/api/3/action/package_show?id={DATASET}'; NATIONAL_SOURCE=f'https://data.gov.ro/dataset/{DATASET}'
CURRENT_YEAR='2026-2027'; LEGACY_YEAR='2025-2026'; REGISTRY='data/school_sources.json'
HEADERS={'User-Agent':'Mozilla/5.0 TransparentaEduRomania/2.2','Accept':'*/*'}
FALLBACK={'SB':{'downloadUrl':'https://docs.google.com/spreadsheets/d/1wwlcVOQJ-H70lx8oV3Kdthb07HLEUlTy/export?format=xlsx','format':'xlsx','schoolYear':LEGACY_YEAR},'TM':{'downloadUrl':'https://www.isj.tm.edu.ro/public/data_files/media/2026/202603251518-Retea%20scolara%20pentru%20site%202026-2027.pdf','format':'pdf','schoolYear':CURRENT_YEAR,'parser':'timis-pdf'}}

def download(url,timeout=90,attempts=3):
 last=None
 for attempt in range(1,attempts+1):
  try:
   print(f'Download {attempt}/{attempts}: {url}'); req=urllib.request.Request(url,headers=HEADERS)
   with urllib.request.urlopen(req,timeout=timeout) as r:data=r.read()
   if not data:raise RuntimeError('Răspuns gol')
   return data
  except Exception as exc:
   last=exc; print(f'Încercarea {attempt} a eșuat: {exc}')
   if attempt<attempts:time.sleep(5*attempt)
 raise RuntimeError(f'Download eșuat: {last}')

def norm(v):
 s='' if v is None else str(v).strip(); s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower(); return re.sub(r'[^a-z0-9]+',' ',s).strip()
def pick(headers,*terms):
 for i,h in enumerate(headers):
  n=norm(h)
  if any(t in n for t in terms):return i
 return None
def val(row,i):return None if i is None or i>=len(row) or row[i] is None else str(row[i]).strip()
def find_header_row(ws):
 for n,row in enumerate(ws.iter_rows(values_only=True),1):
  joined=' | '.join(norm(v) for v in row)
  if ('denumire' in joined or 'nume unit' in joined) and ('judet' in joined or 'localitate' in joined):return n,list(row)
 raise RuntimeError('Antetul rețelei școlare nu a fost găsit.')

def parse_xlsx(raw,source_url,forced_county=None,school_year=LEGACY_YEAR):
 if raw[:2]!=b'PK':raise RuntimeError('Fișierul nu este XLSX valid.')
 wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True); ws=wb[wb.sheetnames[0]]; header_row,headers=find_header_row(ws)
 name_i=pick(headers,'denumire lunga unitate','denumire unitate','denumire','nume unit'); county_i=pick(headers,'judet'); locality_i=pick(headers,'localitate unitate','localitate'); street_i=pick(headers,'strada','adresa'); number_i=pick(headers,'numar'); type_i=pick(headers,'categorie unitate','tip unitate','tipul unit'); medium_i=pick(headers,'mediu loc unitate','mediu'); code_i=pick(headers,'cod sirues','siiir','sirues','cod unit'); status_i=pick(headers,'statut unitate','statut','status'); parent_i=pick(headers,'denumire pj'); schools=[]
 for row in ws.iter_rows(min_row=header_row+1,values_only=True):
  name=val(row,name_i)
  if not name:continue
  county=val(row,county_i) or forced_county; locality=val(row,locality_i); code=val(row,code_i); street=val(row,street_i); number=val(row,number_i); sid=code or 'ro-'+re.sub(r'[^a-z0-9]+','-',norm(f'{county}-{locality}-{name}')).strip('-')[:120]
  schools.append({'id':sid,'sirues':code,'name':name,'county':county,'locality':locality,'address':' '.join(x for x in [street,number] if x) or None,'type':val(row,type_i),'medium':val(row,medium_i),'status':val(row,status_i) or 'official','parentSchool':val(row,parent_i),'schoolYear':school_year,'sourceUrl':source_url})
 return schools

def pdf_text(raw):return '\n'.join((p.extract_text(extraction_mode='layout') or '') for p in PdfReader(io.BytesIO(raw)).pages)
def parse_timisoara_pdf(raw,source_url):
 text=pdf_text(raw); schools=[]
 for block in re.split(r'(?m)(?=^\s*\d+\s+2026-2027\s+TM\s+)',text):
  m=re.match(r'^\s*(\d+)\s+2026-2027\s+TM\s+(.*)',block,re.S)
  if not m:continue
  joined=' '.join(re.sub(r'\s+',' ',x).strip() for x in block.splitlines() if x.strip()); sm=re.search(r'\bUnitate de învățământ\s+(PJ|AR)\b',joined,re.I)
  if not sm:continue
  name=re.sub(r'^\d+\s+2026-2027\s+TM\s+','',joined[:sm.start()].strip())
  if len(name)>3:schools.append({'id':'tm-2026-'+m.group(1),'sirues':None,'name':name,'county':'TM','locality':None,'address':None,'type':None,'medium':None,'status':sm.group(1).upper(),'parentSchool':None,'schoolYear':CURRENT_YEAR,'sourceUrl':source_url,'sourceRow':int(m.group(1))})
 if len(schools)<100:raise RuntimeError(f'PDF Timiș parsare suspectă: {len(schools)}')
 return schools

def clean_pdf_name(line,county):
 name=re.sub(r'^\s*\d{1,4}\s+(?:2026[-–]2027\s+)?(?:'+re.escape(county)+r'\s+)?','',line,flags=re.I)
 name=re.sub(r'\s+(?:Unitate de învățământ\s+)?(?:PJ|AR)\b.*$','',name,flags=re.I)
 # Contact/address columns are frequent in exported SIIIR PDFs and must never become part of a school name.
 name=re.split(r'\b(?:Cod\s+poștal|Cod\s+postal|Telefon|Fax|E-mail|Email|Strada|Str\.|Localitatea|Adres[ăa])\s*:',name,1,flags=re.I)[0]
 name=re.sub(r'\s+\d{6}\s+0\d{8,}\b.*$','',name)
 return re.sub(r'\s+',' ',name).strip(' -|,;')

def valid_school_name(name):
 n=norm(name)
 if len(name)<7 or len(name)>180:return False
 if any(x in n for x in ('cod postal','telefon','email','e mail','inspectoratul scolar','ministerul educatiei')):return False
 if '@' in name or re.search(r'\b(?:www\.|https?://)',name,re.I):return False
 if re.search(r'\b0\d{8,}\b',name):return False
 return bool(re.search(r'\b(scoala|liceu|liceul|colegiu|colegiul|gradinita|seminar|club|palat|centru|centrul)\b',n))

def parse_siiir_pdf(raw,source_url,county,school_year=CURRENT_YEAR):
 text=pdf_text(raw)
 if len(text.strip())<500:raise RuntimeError('PDF fără text extractibil suficient')
 lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines() if x.strip()]; schools=[]; seen=set(); row=0
 for line in lines:
  name=clean_pdf_name(line,county)
  if not valid_school_name(name):continue
  codes=re.findall(r'(?<!\d)(\d{7,12})(?!\d)',line); code=codes[0] if codes else None
  # Postal codes are six digits, so they are deliberately excluded from SIIIR extraction.
  if code and code in name:name=re.sub(r'^\s*'+re.escape(code)+r'\s+','',name).strip()
  if not valid_school_name(name):continue
  key=code or norm(name)
  if key in seen:continue
  seen.add(key); row+=1; sid=code or f'{county.lower()}-{school_year[:4]}-{row}'
  schools.append({'id':sid,'sirues':code,'name':name,'county':county,'locality':None,'address':None,'type':None,'medium':None,'status':'official','parentSchool':None,'schoolYear':school_year,'sourceUrl':source_url,'sourceRow':row})
 if len(schools)<20:raise RuntimeError(f'Parser SIIIR PDF suspect: doar {len(schools)} unități')
 bad=sum(1 for s in schools if not valid_school_name(s['name']))
 if bad:raise RuntimeError(f'Validare nume eșuată: {bad} înregistrări suspecte')
 return schools

def registry_sources():
 with open(REGISTRY,encoding='utf-8') as f:r=json.load(f)
 out=[]
 for j in r.get('jurisdictions',[]):
  if not j.get('importable') or j.get('scope')!='countywide':continue
  src=dict(j); src.update({k:v for k,v in FALLBACK.get(j['code'],{}).items() if k not in src}); urls=src.get('downloads') or ([src.get('downloadUrl')] if src.get('downloadUrl') else [])
  if not urls and src['code'] in FALLBACK:urls=[FALLBACK[src['code']]['downloadUrl']]
  for url in urls:x=dict(src); x['url']=url; out.append(x)
 return out,r

def parse_source(src):
 raw=download(src['url'],120,3); page=src.get('networkUrl') or src['url']; fmt=src.get('format'); parser=src.get('parser')
 if fmt=='xlsx':return parse_xlsx(raw,page,src['code'],src.get('schoolYear',LEGACY_YEAR))
 if parser=='timis-pdf':return parse_timisoara_pdf(raw,page)
 if parser=='siiir-pdf':return parse_siiir_pdf(raw,page,src['code'],src.get('schoolYear',CURRENT_YEAR))
 raise RuntimeError(f"Parser {parser or fmt} pentru {src['code']} nu este validat")

def dedupe(items):
 by={}
 for s in items:
  key=s.get('sirues') or f"{s.get('schoolYear')}|{norm(s.get('county'))}|{norm(s.get('locality'))}|{norm(s.get('name'))}"; old=by.get(key)
  if old is None or (s.get('schoolYear') or '')>(old.get('schoolYear') or ''):by[key]=s
 return list(by.values())

schools=[]; sources=[]; configured,registry=registry_sources(); pages=[{'county':j['code'],'name':j['name'],'page':j.get('networkUrl'),'schoolYear':j.get('schoolYear',CURRENT_YEAR),'status':j.get('status')} for j in registry.get('jurisdictions',[]) if j.get('networkUrl')]
print(f'Surse importabile din registru: {len(configured)} fișiere')
for src in configured:
 try:
  part=parse_source(src); schools.extend(part); sources.append({'county':src['code'],'name':src['name'],'url':src.get('networkUrl') or src['url'],'schoolYear':src.get('schoolYear'),'format':src.get('format'),'count':len(part)}); print(f"{src['code']}: {len(part)} unități importate")
 except Exception as exc:print(f"{src['code']} omis în siguranță: {exc}")
try:
 meta=json.loads(download(API,25,1).decode())['result']; xlsx=next((r for r in meta.get('resources',[]) if str(r.get('format','')).lower()=='xlsx'),None)
 if not xlsx:raise RuntimeError('Resursa XLSX națională lipsește.')
 part=parse_xlsx(download(xlsx['url'],90,2),NATIONAL_SOURCE,school_year=LEGACY_YEAR); schools.extend(part); sources.append({'name':'Ministerul Educației / data.gov.ro','url':NATIONAL_SOURCE,'schoolYear':LEGACY_YEAR,'format':'xlsx','count':len(part)})
except Exception as exc:print(f'Fallback național indisponibil: {exc}')
schools=dedupe(schools)
if not schools:raise SystemExit('Nu s-a putut importa nicio unitate din sursele oficiale.')
current=sum(1 for s in schools if s.get('schoolYear')==CURRENT_YEAR); counties=sorted(set(s.get('county') for s in schools if s.get('county'))); coverage='national-current' if current>=1000 and len(counties)>=42 else ('mixed' if len(counties)>1 else 'partial'); schools.sort(key=lambda x:(x.get('county') or '',x.get('locality') or '',x.get('name') or ''))
out={'schemaVersion':9,'updatedAt':date.today().isoformat(),'targetSchoolYear':CURRENT_YEAR,'coverage':coverage,'importMode':'registry-first','count':len(schools),'currentYearCount':current,'counties':counties,'officialNetworkPages':pages,'sources':sources,'schools':schools}
with open('data/schools.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,separators=(',',':'))
print(f'Import finalizat: {len(schools)} unități; {current} pentru {CURRENT_YEAR}; județe={len(counties)}; acoperire={coverage}.')