"""Bounded offline audit of the frozen v2 raw outputs; zero model calls."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
report_path=root/'evaluation/relevance-result-20261120T232602108784.json'
corpus_path=root/'evaluation/relevance_v2.json'
assert report_path.stat().st_size<1000000 and corpus_path.stat().st_size<20000
report=json.loads(report_path.read_text());corpus=json.loads(corpus_path.read_text())
assert hashlib.sha256(corpus_path.read_bytes()).hexdigest()==report['hashes']['evaluation/relevance_v2.json']
assert len(report['raw_outputs'])==len(corpus['cases'])==4
rows=[]
for case,raw in zip(corpus['cases'],report['raw_outputs']):
 expected={s['id']:s['expected'] for s in case['sources']}
 assert len(raw['assessments'])==4 and {a['source_id'] for a in raw['assessments']}==set(expected)
 for a in raw['assessments']:
  e=expected[a['source_id']]
  rows.append({'source_id':a['source_id'],'expected':e,'actual':{k:a[k] for k in e},'mismatched_fields':[k for k in e if e[k]!=a[k]],'reason':a['reason']})
risks=[r for r in rows if r['expected']['direction'] in {'risk','mixed'}]
distractors=[r for r in rows if r['expected']['relevance'] in {'mention_only','unrelated'}]
out={'scope':'Offline inspection of raw outputs including the rejected fourth batch; not a successful pipeline evaluation. Original labels unchanged.',
 'report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(), 'corpus_sha256':hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
 'live_calls':0,'production_default_changed':False,'pipeline_batches_accepted':len(report['cases']),'pipeline_batches_total':4,
 'raw_label_matches':sum(not r['mismatched_fields'] for r in rows),'raw_labels_total':len(rows),
 'raw_risks_retained':sum(r['actual']['relevance']=='evidence' and r['actual']['direction'] in {'risk','mixed'} for r in risks),'risk_total':len(risks),
 'raw_distractors_identified':sum(r['actual']['relevance'] in {'mention_only','unrelated'} for r in distractors),'distractor_total':len(distractors),
 'rows':rows,'interpretation_notes':[
 'A counterexample at 3 pm refutes all-interval quiet without observing the full interval. The original partial label is preserved, but coverage semantics require independent review.',
 'Quiet at 7 pm and noisy at 9 pm was labeled risk instead of mixed. Full source is locally retained, but classification omitted the positive direction.',
 'Ambiguous attribution labels differ on direction and coverage; uncertainty must never be promoted into candidate-specific fact.',
 'Weekend risk received evidence/none/none and was rejected. No filtering is enabled.']}
(root/'evaluation/relevance-v2-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in {'rows','interpretation_notes'}},indent=2))
