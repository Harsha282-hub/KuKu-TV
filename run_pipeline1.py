"""Offline Kuku TV promo scoring; Python 3.9+, standard library only.

Uses existing main.get_shortlisted_clips() when --from-main is supplied;
otherwise loads the exported shortlisted_clips.json snapshot.
"""
import argparse
import csv
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
WEIGHTS = {'hook_score': .35, 'cliffhanger_score': .30, 'clarity_score': .25, 'emotion_score': .10}

# Scores from the earlier screenplay editorial reviews. These are NOT API scores.
REVIEWED = {
 1:(7,5.5,6.5,8.5),2:(8,7.5,9,9),3:(6.5,6,7.5,9),4:(7,5,7,8.5),5:(5.5,9,8.5,7.5),
 6:(7,6.5,8,8.5),7:(8,7,9,9),8:(7.5,7.5,8.5,8.5),9:(9.5,8,9.5,9),10:(8.5,8,9,9),
 11:(9,7.5,8.5,9),12:(6.5,8.5,8,8),13:(7.5,8,9,8.5),14:(6,9.5,7.5,8.5),
 15:(6,4.5,7.5,7),16:(6.5,4,8,8),17:(6.5,7,7,7.5),18:(8,4,8,8),19:(7,7,7.5,8),20:(7,6.5,7.5,7.5),
 21:(9,8.5,9,9.5),22:(8,5,8.5,9),23:(8,7,9,9),24:(6,6,7,7),25:(5,3.5,7.5,7)
}
STRONG = re.compile(r'kill|dead|die|gallows|hang|poison|murder|burn|fire|witch|arrest|attack|blood|threat|betray|disown|secret|truth|never|stop|help|save|danger|destroy|trial|scream|terrified|shatter|wound|stolen|knife|weapon',re.I)
EMOTIONAL = re.compile(r'kill|dead|death|die|blood|hurt|wound|burn|fire|flame|poison|witch|gallows|hang|arrest|guard|threat|attack|knife|weapon|betray|humiliat|disown|inherit|dowry|steal|stolen|lie|liar|secret|truth|never|marry|marriage|wedding|leave|refuse|stop|don.t|no!|help|save|danger|destroy|father|mother|duke|duchess|trial|murder|forgiv|shatter|cry|tears|shock|gasp|scream|fear|terrified|trembl|kiss|love|pregnan|child|son|daughter|husband|wife|ledger|ring',re.I)
QUESTION = re.compile(r'\?|what happens|what will|who |why |where |how |until|before|unless|if you|if she|if he|no one knows|unrevealed|unknown|secret|reveals|discover|realiz|suddenly|abruptly|unexpected|freez|stops short',re.I)
RESOLVED = re.compile(r'walk away|walk off|leave together|safely|finally safe|relief|embrac|comfort|reassur|all is well|smil|settle|kiss|resolved|the end|thank',re.I)
SETUP = re.compile(r'wide shot|establishing|landscape|sunlight|forest|cottage|quiet|calm|walking|sun-dappled|panoram',re.I)

def clamp(value):
    return round(max(1,min(10,value))*2)/2

def text_of(event):
    return re.sub(r'\s+',' ',event.get('text','')).strip().strip('"')

def load_candidates(from_main):
    if not from_main:
        return json.loads((BASE/'data'/'shortlisted_clips.json').read_text(encoding='utf-8'))
    from main import get_shortlisted_clips  # user's existing extractor; do not modify it
    clips = get_shortlisted_clips()
    return [dict(clip_id=i,episode=c['episode'],start=c['start'],end=c['end'],duration=c['duration'],
                 events=[e for e in c['events'] if e['start']>=c['start'] and e['end']<=c['end']])
            for i,c in enumerate(clips,1)]

def evaluate(c):
    start,end = c['start'],c['end']
    ev = sorted(c['events'],key=lambda e:(e['start'],e['end']))
    first = [e for e in ev if e['start']<=start+3 and e['end']>=start] or ev[:2]
    last = [e for e in ev if end-7<=e['start']<=end] or ev[-2:]
    first_txt = ' '.join(map(text_of,first))
    last_txt = ' '.join(map(text_of,last))
    all_txt = ' '.join(map(text_of,ev))
    dialog = [e for e in ev if e.get('type')=='dialogue']
    first_dialog = [e for e in first if e.get('type')=='dialogue']
    last_dialog = [e for e in last if e.get('type')=='dialogue']
    cf,cl = len(STRONG.findall(first_txt)),len(STRONG.findall(last_txt))
    emotional,strong = len(EMOTIONAL.findall(all_txt)),len(STRONG.findall(all_txt))
    questions = len(QUESTION.findall(last_txt))
    resolved = bool(RESOLVED.search(last_txt))
    hook = clamp(4+min(3,cf)*1.05+(.85 if first_dialog else 0)+(.5 if '?' in first_txt else 0)-(.75 if SETUP.search(first_txt) and not cf else 0))
    cliff = clamp(4.3+min(2,cl)*.85+min(2,questions)*.7+(.65 if last_dialog and '?' in last_txt else 0)-(1.25 if resolved else 0))
    clarity = clamp(5+min(3,len(dialog))*.6+(.6 if len({e.get('speaker') for e in dialog if e.get('speaker')})>1 else 0)+(.5 if len(all_txt)>350 else 0)-(.6 if not dialog else 0))
    emotion = clamp(4+min(6,strong)*.55+min(6,emotional)*.12+(.5 if re.search(r'cry|tear|sob|trembl|gasp|shock|pain|heart|love|kiss|wound|blood',all_txt,re.I) else 0))
    reviewed = c['clip_id'] in REVIEWED
    if reviewed:
        hook,cliff,clarity,emotion = REVIEWED[c['clip_id']]
    overall = round(hook*.35+cliff*.30+clarity*.25+emotion*.10+1e-9,2)
    def evidence(es,last=False):
        preferred = [e for e in es if e.get('type')=='dialogue']
        chosen = (preferred[-1] if last else preferred[0]) if preferred else (es[-1] if last else es[0]) if es else None
        return text_of(chosen)[:220] if chosen else ''
    return dict(clip_id=c['clip_id'],episode=c['episode'],start=c['start'],end=c['end'],duration=c['duration'],
                hook_score=hook,cliffhanger_score=cliff,clarity_score=clarity,emotion_score=emotion,overall_score=overall,
                hook=evidence(first),cliffhanger=evidence(last,True),
                rationale=('Previously reviewed screenplay candidate' if reviewed else 'Preliminary keyword/structure-based screening; manually verify hook, end beat and clarity'),
                assessment_type=('Prior editorial review' if reviewed else 'Preliminary heuristic estimate'))

def write_csv(path, rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    parser=argparse.ArgumentParser(description='Offline Kuku TV promo pipeline')
    parser.add_argument('--from-main',action='store_true',help='Use existing main.py get_shortlisted_clips() rather than bundled snapshot')
    args=parser.parse_args()
    candidates=load_candidates(args.from_main)
    ids=[c['clip_id'] for c in candidates]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate clip IDs')
    for c in candidates:
        if not 20<=c['duration']<=60:raise ValueError(f'Invalid duration for clip {c["clip_id"]}')
    rows=[evaluate(c) for c in candidates]
    ranked=sorted(rows,key=lambda r:(-r['overall_score'],-r['cliffhanger_score'],-r['hook_score'],r['clip_id']))
    for i,row in enumerate(ranked,1):row['rank']=i
    out=BASE/'results';out.mkdir(exist_ok=True)
    (out/'all_evaluations.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
    write_csv(out/'ranked_promos.csv',ranked)
    selection_path=BASE/'data'/'curated_top20.json'
    selected=[]
    if selection_path.exists():
        curated=json.loads(selection_path.read_text(encoding='utf-8'))
        by_id={r['clip_id']:r for r in rows}
        for item in curated:
            if item['clip_id'] not in by_id:raise ValueError(f'Curated clip {item["clip_id"]} missing')
            selected.append({**item,**{f'current_{k}':v for k,v in by_id[item['clip_id']].items() if k in ('overall_score','assessment_type')}})
        for i,a in enumerate(selected):
            for b in selected[i+1:]:
                if a['episode']==b['episode'] and max(a['start'],b['start'])<min(a['end'],b['end']):
                    raise ValueError('Overlapping curated clips')
        write_csv(out/'final_top20.csv',selected)
        (out/'final_top20.json').write_text(json.dumps(selected,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Processed {len(rows)} clips; curated {len(selected)}; outputs in {out}')
    print('No API key, network, or paid credits required.')

if __name__=='__main__':main()
