#!/usr/bin/env python3
"""Import public professional teacher data from official Romanian education reports.
Teacher-school links are only created when the official source explicitly names the placement.
"""
import json,re,urllib.request,urllib.parse,time,html as H
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'teachers.json'
COUNTIES=['AB','AR','AG','BC','BH','BN','BT','BV','BR','B','BZ','CS','CL','CJ','CT','CV','DB','DJ','GL','GR','GJ','HR','HD','IL','IS','IF','MM','MH','MS','NT','OT','PH','SM','SJ','SB','SV','TR','TM','TL','VS','VL','VN']
UA={'User-Agent':'Mozilla/5.0 (compatible; TransparenEdu/1.2)','Accept':'text/html,application/xhtml+xml'}

def get(url,retries=4,timeout=30):
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers=UA)
            with urllib.request.urlopen(req,timeout=timeout) as r:return r.read().decode('utf-8','replace')
        except Exception as e:
            last=e
            if attempt+1<retries:time.sleep(2**attempt)
    raise last

def text(src):
    src=re.sub(r'<script[\s\S]*?</script>',' ',src,flags=re.I);src=re.sub(r'<style[\s\S]*?</style>',' ',src,flags=re.I);src=re.sub(r'<[^>]+>',' ',src)
    return re.sub(r'\s+',' ',H.unescape(src)).strip()

def candidate_pages(county):
    roots=[f'https://definitivat.edu.ro/2026/generated/files/j/{county}/',f'https://titularizare.edu.ro/2026/generated/files/j/{county}/',f'https://static.titularizare.edu.ro/2026/generated/files/j/{county}/']
    paths=['np_d_nip/index.html','np_nip/index.html','ci_d_nip/index.html','ci_nip/index.html','po_ludo/index.html','pcnt_lud/index.html','candpretet1/index.html']
    for root in roots:
        for p in paths:yield urllib.parse.urljoin(root,p)

def find_result_page(county):
    for u in candidate_pages(county):
        try:
            t=text(get(u,2,20))
            if len(t)>300 and any(k in t for k in ('Incadrare','Încadrare','PROFESOR','Profesor')):return u,t
        except Exception:pass
    return None,None

def parse(county,url,t):
    starts=list(re.finditer(r'(?<!\d)(\d{3,6})\s+([A-ZĂÂÎȘŞȚŢ][A-ZĂÂÎȘŞȚŢ .\-]+?)\s+(\d+(?:[\.,]\d+)?)\s+(?:Nu|Da)\s+',t))
    rows=[]
    for i,m in enumerate(starts):
        block=t[m.start():(starts[i+1].start() if i+1<len(starts) else min(len(t),m.start()+5000))]
        name=re.sub(r'\s+',' ',m.group(2)).strip(' -');inc=re.search(r'1\.\s*(.{2,120}?)\s+2\.\s*(.{3,220}?)\s+3\.',block,re.I);role=re.search(r'4\.\s*(PROFESOR|EDUCATOARE?|ÎNVĂȚĂTOARE?|INVATATOARE?|MAISTRU INSTRUCTOR|INSTITUTOR)',block,re.I)
        if not inc or not role:continue
        locality=re.sub(r'\s+',' ',inc.group(1)).strip();school=re.sub(r'\s+',' ',inc.group(2)).strip()
        if len(school)<4 or school in {'-','.'}:continue
        subj='Nespecificată';mm=re.search(r'(?:Nota examen|Disciplina de examen)\s+(.{3,180}?)\s+1\.',block,re.I)
        if mm:subj=re.sub(r'\s+',' ',mm.group(1)).strip().title()
        rows.append({'id':f'def26-{county.lower()}-{m.group(1)}','name':name.title(),'subject':subj,'schoolId':None,'schoolNameOfficial':school,'county':county,'locality':locality,'profileStatus':'official-professional-data','schoolLinkStatus':'official-placement-unmatched','officialResults':[{'type':'definitivat','year':2026,'writtenGrade':float(m.group(3).replace(',','.')),'sourceUrl':url}],'rating':None,'reviewCount':0})
    return rows

def main():
    allrows=[];stats={}
    for c in COUNTIES:
        try:
            u,t=find_result_page(c)
            if not u:stats[c]={'status':'page-not-resolved','count':0};print(c,'NO PAGE',flush=True);continue
            rows=parse(c,u,t);allrows.extend(rows);stats[c]={'status':'ok' if rows else 'parsed-zero','count':len(rows),'url':u};print(c,len(rows),u,flush=True)
        except Exception as e:stats[c]={'status':'error','count':0,'error':str(e)[:180]};print(c,'ERROR',e,flush=True)
    if not allrows and OUT.exists():
        try:
            old=json.loads(OUT.read_text(encoding='utf-8'))
            if old.get('count',0)>0:raise SystemExit('Import returned zero records; preserving previous database.')
        except json.JSONDecodeError:pass
    data={'schemaVersion':5,'updatedAt':date.today().isoformat(),'sourceYear':2026,'coverage':'official-education-sources','linkingPolicy':'School links require an explicit official current-placement field and a separate exact school-registry match; name-only teacher matching is forbidden.','count':len(allrows),'jurisdictionsAttempted':len(COUNTIES),'importStats':stats,'teachers':allrows}
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('TOTAL',len(allrows),flush=True)
if __name__=='__main__':main()
