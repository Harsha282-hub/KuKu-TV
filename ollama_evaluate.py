"""Resumable local-LLM evaluation for Kuku TV. Python 3.9+, no pip packages.

Uses Ollama's localhost API; screenplay data never needs to leave the machine.
Existing run_pipeline.py and main.py remain unchanged.
"""
import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib import error, request

BASE = Path(__file__).resolve().parent
WEIGHTS = {'hook_score': .35, 'cliffhanger_score': .30, 'clarity_score': .25, 'emotion_score': .10}
FIELDS = tuple(WEIGHTS)
VERSION = 'kuku-judge-v1.1'
SYSTEM = '''You are a critical short-form drama promo editor. Evaluate ONLY the supplied screenplay events, not imagined video. Score four independent criteria from 1.0 to 10.0: hook_score = immediate first THREE seconds; cliffhanger_score = unresolved suspense in the final SEVEN seconds; clarity_score = comprehensible without prior episode context; emotion_score = emotional impact. Be strict: slow setup or no relevant dialogue in first three seconds should lower hook; a resolved ending should lower cliffhanger. Judge event timing carefully. Output JSON only with keys hook_score, cliffhanger_score, clarity_score, emotion_score, rationale, hook_evidence, cliffhanger_evidence, needs_video_review. Evidence must quote or accurately paraphrase supplied events. Scores may have one decimal place. Never assume any event occurred outside the supplied timestamps.'''

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def payload(clip):
    events = []
    for e in sorted(clip['events'], key=lambda x: (x['start'], x['end'], x.get('type',''))):
        events.append({'start': e['start'], 'end': e['end'], 'type': e.get('type'),
                       'speaker': e.get('speaker'), 'text': e.get('text','')})
    return {'episode': clip['episode'], 'start': clip['start'], 'end': clip['end'],
            'duration': clip['duration'], 'first_three_seconds_end': round(clip['start'] + 3, 2),
            'final_seven_seconds_start': round(clip['end'] - 7, 2), 'events': events}

def signature(clip, model, temperature):
    content = json.dumps({'version': VERSION, 'model': model, 'temperature': temperature,
                          'system': SYSTEM, 'clip': payload(clip)}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def parse_judgment(raw):
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I)
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise ValueError('Response is not a JSON object')
    out = {}
    for field in FIELDS:
        val = raw.get(field)
        if isinstance(val, bool) or not isinstance(val, (int,float)) or not 1 <= val <= 10:
            raise ValueError(f'{field} must be a number between 1 and 10, got {val!r}')
        out[field] = round(float(val), 2)
    for field in ('rationale','hook_evidence','cliffhanger_evidence'):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ValueError(f'Missing nonempty {field}')
        out[field] = raw[field].strip()[:1200]
    out['needs_video_review'] = bool(raw.get('needs_video_review', True))
    out['overall_score'] = round(sum(out[k]*w for k,w in WEIGHTS.items()), 3)
    return out

def call_ollama(base_url, model, clip, temperature, seed, timeout):
    url = base_url.rstrip('/') + '/api/chat'
    body = {'model': model, 'stream': False, 'format': 'json',
            'options': {'temperature': temperature, 'seed': seed, 'num_ctx': 8192},
            'messages': [{'role':'system','content':SYSTEM},
                         {'role':'user','content':'Score this screenplay clip. Return the specified JSON fields.\n'+json.dumps(payload(clip),ensure_ascii=False)}]}
    req = request.Request(url, data=json.dumps(body).encode('utf-8'),
                          headers={'Content-Type':'application/json'}, method='POST')
    with request.urlopen(req, timeout=timeout) as response:
        data = json.load(response)
    return parse_judgment(data['message']['content'])

def write_csv(path, rows):
    if not rows: return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def export(candidates, cache_dir, out_dir, model, temperature):
    completed = []
    for c in candidates:
        key = signature(c,model,temperature)
        path = cache_dir / f"clip_{c['clip_id']:03d}_{key[:16]}.json"
        if not path.exists(): continue
        try:
            entry = load(path)
            if entry.get('signature') != key: continue
            scores = parse_judgment(entry['evaluation'])
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
        completed.append({'clip_id': c['clip_id'], 'episode': c['episode'],
                          'start': c['start'], 'end': c['end'], 'duration': c['duration'],
                          **scores, 'model': model, 'assessment_type': 'Local LLM (unverified by human)'})
    ranked = sorted(completed,key=lambda x:(-x['overall_score'],-x['cliffhanger_score'],-x['hook_score'],x['clip_id']))
    for i,row in enumerate(ranked,1): row['llm_rank'] = i
    atomic_json(out_dir/'ollama_evaluations.json', ranked)
    write_csv(out_dir/'ollama_ranked_promos.csv', ranked)
    return len(completed)

def main():
    p=argparse.ArgumentParser(description='Local Ollama promo scoring, cached and resumable')
    p.add_argument('--input',type=Path,default=BASE/'data'/'shortlisted_clips.json')
    p.add_argument('--model',default='qwen2.5:7b')
    p.add_argument('--url',default='http://127.0.0.1:11434')
    p.add_argument('--temperature',type=float,default=0.0)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--timeout',type=int,default=300)
    p.add_argument('--retries',type=int,default=3)
    p.add_argument('--limit',type=int,default=0,help='Process only first N clips; 0 means all')
    p.add_argument('--cache-dir',type=Path,default=BASE/'cache'/'ollama')
    p.add_argument('--output-dir',type=Path,default=BASE/'results')
    p.add_argument('--export-only',action='store_true')
    args=p.parse_args()
    if not 0<=args.temperature<=2: p.error('temperature must be 0 to 2')
    candidates=load(args.input)
    ids=[c['clip_id'] for c in candidates]
    if len(set(ids))!=len(ids): p.error('duplicate clip IDs')
    if args.limit: candidates=candidates[:args.limit]
    args.cache_dir.mkdir(parents=True,exist_ok=True)
    failed=[]; reused=0; newly=0
    if not args.export_only:
        for i,c in enumerate(candidates,1):
            key=signature(c,args.model,args.temperature)
            path=args.cache_dir/f"clip_{c['clip_id']:03d}_{key[:16]}.json"
            if path.exists():
                try:
                    old=load(path)
                    if old.get('signature')==key: parse_judgment(old['evaluation']); reused+=1; print(f'[{i}/{len(candidates)}] clip {c["clip_id"]}: cached',flush=True); continue
                except (ValueError,KeyError,json.JSONDecodeError): pass
            for attempt in range(args.retries+1):
                try:
                    result=call_ollama(args.url,args.model,c,args.temperature,args.seed,args.timeout)
                    atomic_json(path,{'signature':key,'clip_id':c['clip_id'],'model':args.model,
                                      'temperature':args.temperature,'evaluation':result})
                    newly+=1
                    print(f'[{i}/{len(candidates)}] clip {c["clip_id"]}: {result["overall_score"]:.2f}',flush=True)
                    break
                except (error.URLError,TimeoutError,ValueError,KeyError,json.JSONDecodeError) as exc:
                    if attempt==args.retries:
                        failed.append({'clip_id':c['clip_id'],'error':str(exc)})
                        print(f'[{i}/{len(candidates)}] FAILED clip {c["clip_id"]}: {exc}',file=sys.stderr,flush=True)
                    else:
                        wait=min(30,2**attempt)+random.Random(args.seed+c['clip_id']+attempt).uniform(0,.3)
                        print(f'clip {c["clip_id"]}: retry {attempt+1}/{args.retries} in {wait:.1f}s ({exc})',flush=True)
                        time.sleep(wait)
    total=export(candidates,args.cache_dir,args.output_dir,args.model,args.temperature)
    if failed: atomic_json(args.output_dir/'ollama_failures.json',failed)
    print(f'Complete: {total}/{len(candidates)} evaluated, {newly} new, {reused} cached, {len(failed)} failed.')
    print('Results:',args.output_dir/'ollama_ranked_promos.csv')
    if failed: sys.exit(1)

if __name__=='__main__':main()
