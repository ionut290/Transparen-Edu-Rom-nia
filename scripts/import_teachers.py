#!/usr/bin/env python3
"""Import public professional teacher data from official Definitivat 2026 reports.
Runs in COUNTY_BATCH groups and preserves previous batches.
Uses curl with IPv4 and paginated official report pages to avoid urllib/GitHub runner stalls.
"""
import json,re,subprocess,time,html as H,os
from html.parser import HTMLParser
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'teachers.json'
ALL_COUNTIES=['AB','AR','AG','BC','BH','BN','BT','BV','BR','B','BZ','CS','CL','CJ','CT','CV','DB','DJ','GL','GR','GJ','HR','HD','IL','IS','IF','MM','MH','MS','NT','OT','PH','SM','SJ','SB','SV','TR','TM','TL','VS','VL','VN']
COUNTIES=[x.strip() for x in os.getenv('COUNTY_BATCH','').split(',') if x.strip()] or ALL_COUNTIES
UA='Mozilla/5.0 (compatible; TransparenEdu/1.5)'

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='tr': self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]
        elif tag=='br' and self.cell is not None:self.cell.append('\n')
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in ('td','th') and self.cell is not None:
            self.row.append(re.sub(r'[ \t\r\f\v]+',' ',' '.join(self.cell)).strip());self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None

def get(url):
    last='download failed'
    for attempt in range(2):
        try:
            p=subprocess.run(['curl','-4','-L','--fail','--silent','--show-error','--connect-timeout','8','--max-time','20','--retry','1','--retry-delay','1','-A',UA,url],capture_output=True,timeout=28)
            if p.returncode==0 and len(p.stdout)>200:return p.stdout.decode('utf-8','replace')
            last=(p.stderr.decode('utf-8','replace') or f'curl exit {p.returncode}').strip()
        except Exception as e:last=str(e)
        time.sleep(1)
    raise RuntimeError(last[:180])

def base_url(county):return f'https://www.definitivat.edu.ro/2026/generated/files/j/{county}/ci_nip/'
def clean(s):return re.sub(r'\s+',' ',H.unescape(str(s or ''))).strip()

def placement_parts(cell):
    t=clean(cell)
    m=re.search(r'1\.\s*(.*?)\s+2\.\s*(.*?)\s+3\.\s*(.*?)\s+4\.\s*(.*?)(?:\s+1\.|$)',t,re.I)
    if not m:return None,None,None
    return clean(m.group(1)),clean(m.group(2)),clean(m.group(4))

def parse(county,url,src):
    p=TableParser();p.feed(src);rows=[]
    for cells in p.rows:
        if len(cells)<4:continue
        code=clean(cells[0])
        if not re.fullmatch(r'\d{3,6}',code):continue
        name=clean(cells[1]);subject=clean(cells[2]);locality,school,role=placement_parts(cells[3])
        if not name or not subject or not school or len(school)<4:continue
        if not role or not any(k in role.upper() for k in ('PROFESOR','EDUCATO','INVATATO','ÎNVĂȚĂTO','INSTITUTOR','MAISTRU')):continue
        rows.append({'id':f'def26-{county.lower()}-{code}','name':name.title(),'subject':subject.title(),'schoolId':None,'schoolNameOfficial':school,'county':county,'locality':locality,'profileStatus':'official-professional-data','schoolLinkStatus':'official-placement-unmatched','officialResults':[{'type':'definitivat-registration','year':2026,'sourceUrl':url}],'rating':None,'reviewCount':0})
    return rows

def import_county(c):
    base=base_url(c);found={};errors=[]
    # The official index can be slow from cloud runners. Page files are independently accessible.
    for n in range(1,41):
        u=f'{base}page_{n}.html'
        try:src=get(u)
        except Exception as e:
            errors.append(str(e));
            if n==1:continue
            # two consecutive missing/timed-out pages after data usually means the report ended
            if found and len(errors)>=2:break
            continue
        rows=parse(c,u,src)
        if not rows:
            if found:break
            continue
        for r in rows:found[r['id']]=r
        errors=[]
    return list(found.values()),errors[-1] if errors else None

def main():
    old={}
    if OUT.exists():
        try:old=json.loads(OUT.read_text(encoding='utf-8'))
        except json.JSONDecodeError:old={}
    kept=[x for x in old.get('teachers',[]) if x.get('county') not in COUNTIES]
    stats=dict(old.get('importStats',{}));fresh=[]
    print('BATCH',','.join(COUNTIES),flush=True)
    for c in COUNTIES:
        try:
            rows,err=import_county(c);fresh.extend(rows)
            stats[c]={'status':'ok' if rows else 'download-unavailable','count':len(rows),'baseUrl':base_url(c)}
            if err:stats[c]['lastError']=err
            print(c,len(rows),stats[c]['status'],flush=True)
        except Exception as e:
            stats[c]={'status':'error','count':0,'error':str(e)[:180],'baseUrl':base_url(c)};print(c,'ERROR',e,flush=True)
    allrows=kept+fresh
    data={'schemaVersion':8,'updatedAt':date.today().isoformat(),'sourceYear':2026,'coverage':'official-definitivat-current-placement','linkingPolicy':'School links require an explicit official current-placement field and a separate exact school-registry match; name-only teacher matching is forbidden.','count':len(allrows),'jurisdictionsAttempted':len(stats),'lastBatch':COUNTIES,'importStats':stats,'teachers':allrows}
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('BATCH TOTAL',len(fresh),'DATABASE TOTAL',len(allrows),flush=True)
if __name__=='__main__':main()
