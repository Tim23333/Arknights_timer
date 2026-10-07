"""Extend three explicitly reviewed standard source formulas; no frozen helper edits."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DIR=ROOT/'tools/trace_audit';OUT=ROOT/'validation/trace_audit/simple_formulas_v5'
RULES={'rule/ark_time_quantize','rule/ark_ability_windup','rule/ark_deploy_refund'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,s):
 p=DIR/name;assert not p.exists();p.write_text(s,encoding='utf8',newline='')
def main():
 math=(DIR/'stream_oracle_v4_math.py').read_text();old=' n=number\n';new=""" n=number
 if rule=='rule/ark_time_quantize':
  seconds=n(inputs['seconds']);quantum=n(inputs['quantum']);digits=params['ratio_digits'];integer(digits,'ratio digits')
  if seconds<0 or quantum<=0:raise ValueError('nonnegative seconds and positive quantum required')
  return __import__('math').ceil(round(seconds/quantum,digits))
 if rule=='rule/ark_ability_windup':return n(inputs['timing_parameters']['seconds'])
""";assert math.count(old)==1;write('stream_oracle_v5_math.py',math.replace(old,new))
 identity=(DIR/'stream_oracle_v4_identity.py').read_text().replace('stream_oracle_v4_math as base','stream_oracle_v5_math as base');write('stream_oracle_v5_identity.py',identity)
 public=(DIR/'stream_oracle_v4.py').read_text().replace('stream_oracle_v4_identity','stream_oracle_v5_identity').replace('stream_oracle_v4_math','stream_oracle_v5_math').replace('stream-audit/v4','stream-audit/v5');write('stream_oracle_v5.py',public)
 assert not OUT.exists();OUT.mkdir(parents=True);pins=json.loads((ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json').read_bytes());cp=Path('E:/ArkSimEvidence/campaign/05_09_8fa4e36752e92f7d/public_v1.checkpoint.json');ref=json.loads(cp.read_bytes())['kernel']['events']['reference'];found={};selected=OUT/'actual_source_examples.jsonl'
 with Path(ref['path']).open('rb') as f,selected.open('xb') as out:
  for line in f:
   e=json.loads(line);t=e.get('payload',{}).get('trace',{});rid=t.get('rule_id')
   if e['type']=='calculation' and rid in RULES and rid not in found:
    found[rid]=e;out.write(line)
 assert set(found)==RULES;standard=ROOT.parent/'unpack_work/campaign_chapter05_complete_v3_candidate/ark_sim/content/presets/ark_standard.json';assert sha(standard)=='1070ba6793cee5ded71c0f0b89a96ba72973d49989407e70a858a575febb9814';defs={r['id']:r for r in json.loads(standard.read_bytes())['rules']}
 for rid,e in found.items():
  t=e['payload']['trace'];d=defs[rid];assert t['parameters']==d.get('parameters',{}) and t['stages'][-1]['expression']==d['implementation']['expression'];pins['rules'][rid]={'formula_version':'independent-source-arithmetic/v5','contract':d['contract'],'rule_fingerprint':t['rule_fingerprint'],'expression':d['implementation']['expression'],'provider':None,'evidence':'Pinned standard source1070... and independently written ceil(round ratio), direct source seconds, and refund algebra; captured outputs are not expected values.'}
 pins['added_formula_actual_occurrences_in_sealed_05_09']={'rule/ark_time_quantize':36484,'rule/ark_ability_windup':233,'rule/ark_deploy_refund':11};pins['parent_pin_sha']=sha(ROOT/'validation/trace_audit/source_golden_v2/oracle_pins.json');pins['source_actual_checkpoint_journal_reference']=ref;dest=OUT/'oracle_pins.json';dest.write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'new_pins_sha':sha(dest),'real_examples_sha':sha(selected),'counts':pins['added_formula_actual_occurrences_in_sealed_05_09']}))
if __name__=='__main__':main()
