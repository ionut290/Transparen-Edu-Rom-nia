#!/usr/bin/env python3
"""Import public professional teacher data from official Romanian education reports.

The importer intentionally uses Definitivat current-placement fields for school links.
It never joins a teacher to a school by name alone.
"""
import json, re, unicodedata, urllib.request
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'teachers.json'
COUNTIES=['AB','AR','AG','BC','BH','BN','BT','BV','BR','B','BZ','CS','CL','CJ','CT','CV','DB','DJ','GL','GR','GJ','HR','HD','IL','IS','IF','MM','MH','MS','NT','OT','PH','SM','SJ','SB','SV','TR','TM','TL','VS','VL','VN']
UA={'User-Agent':'Mozilla/5.0 TransparenEdu/1.0'}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read().decode('utf-8','replace')

def text(html):
    html=re.sub(r'<script[\s\S]*?</script>',' ',html,flags=re.I)
    html=re.sub(r'<style[\s\S]*?</style>',' ',html,flags=re.I)
    html=re.sub(r'<[^>]+>',' ',html)
    import html as H
    return re.sub(r'\s+',' ',H.unescape(html)).strip()

def slug(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','-',s).strip('-')[:80]

def find_result_page(county):
    base=f'https://definitivat.edu.ro/generated/files/j/{county}/index.html'
    h=get(base)
    # Prefer final results ordered by discipline/name. Official pages link to a nested index.
    links=re.findall(r'href=["\']([^"\']+)["\']',h,re.I)
    candidates=[x for x in links if 'index.html' in x and x!='index.html']
    for rel in candidates:
        u=urllib.parse.urljoin(base,rel)
        try:
            t=text(get(u))
            if 'Rezultatele finale' in t and 'Incadrare curent' in t:return u,t
        except Exception: pass
    return None,None

def parse(county,url,t):
    # Conservative row parser: accept only records containing explicit current locality + school + teaching role.
    starts=list(re.finditer(r'(?<!\d)(\d{3,6})\s+([A-ZĂÂÎȘŞȚŢ][A-ZĂÂÎȘŞȚŢ .\-]+?)\s+(\d+(?:\.\d+)?)\s+(?:Nu|Da)\s+',t))
    rows=[]
    for i,m in enumerate(starts):
        block=t[m.start():(starts[i+1].start() if i+1<len(starts) else min(len(t),m.start()+5000))]
        name=re.sub(r'\s+',' ',m.group(2)).strip(' -')
        inc=re.search(r'1\.\s*([^\n]{2,100}?)\s+2\.\s*([^\n]{3,180}?)\s+3\.',block)
        role=re.search(r'4\.\s*(PROFESOR|EDUCATOARE?|ÎNVĂȚĂTOARE?|INVATATOARE?|MAISTRU INSTRUCTOR|INSTITUTOR)',block,re.I)
        if not inc or not role: continue
        locality=re.sub(r'\s+',' ',inc.group(1)).strip()
        school=re.sub(r'\s+',' ',inc.group(2)).strip()
        if len(school)<4 or school in {'-','.'}: continue
        subj=''
        mm=re.search(r'(?:Nota examen|Disciplina de examen)\s+([A-ZĂÂÎȘŞȚŢ0-9 ,\-]+?)\s+1\.',block,re.I)
        if mm: subj=re.sub(r'\s+',' ',mm.group(1)).strip()
        rows.append({'id':f'def26-{county.lower()}-{m.group(1)}','name':name.title(),'subject':subj.title() if subj else 'Nespecificată','schoolId':None,'schoolNameOfficial':school,'county':county,'locality':locality,'profileStatus':'official-professional-data','schoolLinkStatus':'official-placement-unmatched','officialResults':[{'type':'definitivat','year':2026,'writtenGrade':float(m.group(3)),'sourceUrl':url}],'rating':None,'reviewCount':0})
    return rows

def main():
    allrows=[]; stats={}
    for c in COUNTIES:
        try:
            u,t=find_result_page(c)
            if not u: stats[c]={'status':'page-not-resolved','count':0};continue
            rows=parse(c,u,t); allrows.extend(rows);stats[c]={'status':'ok','count':len(rows),'url':u}
            print(c,len(rows),u,flush=True)
        except Exception as e:
            stats[c]={'status':'error','count':0,'error':str(e)[:160]};print(c,'ERROR',e,flush=True)
    data={'schemaVersion':3,'updatedAt':date.today().isoformat(),'sourceYear':2026,'coverage':'official-definitivat','linkingPolicy':'School links require an explicit official current-placement field and a separate exact school-registry match; name-only teacher matching is forbidden.','count':len(allrows),'jurisdictionsAttempted':len(COUNTIES),'importStats':stats,'teachers':allrows}
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('TOTAL',len(allrows))
if __name__=='__main__':
    import urllib.parse
    main()
