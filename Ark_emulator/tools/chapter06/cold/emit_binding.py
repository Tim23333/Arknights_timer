"""Verify exact native numeric values against compiled-content binding profiles."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'packages/campaign/chapter06_cold'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    numeric=OUT/'numeric.sources.json';model=OUT/'model.json'
    n=json.loads(numeric.read_bytes());m=json.loads(model.read_bytes())
    values=n['values'];bindings=[]
    for item in values:
        seconds=item['value']
        if item['key'].endswith('freeze'):
            ability=next(a for a in m['abilities'] if a['id']=='ability/ch6/cold/apply'+str(int(seconds)))
            effect=ability['timeline'][0]['effect']
            if effect['parameters']['duration_seconds']!=seconds or effect['op']!='buff_application':raise ValueError('Source duration differs from actual module')
            bindings.append({'source_path':item['path'],'source_key':item['key'],'source_value':seconds,'module_ability':ability['id'],'module_application_rule':effect['application_rule']})
        else:
            rule=next(r for r in m['rules'] if r['id']=='rule/ch6/cold/frozen_atkscale'+str(seconds))
            if rule['parameters']['atk_scale']!=seconds or rule['contract']!='damage.request':raise ValueError('TARGETFROZEN scale differs')
            bindings.append({'source_path':item['path'],'source_key':item['key'],'source_value':seconds,'module_rule':rule['id'],'module_buff':'buff/ch6/cold/frozen_atkscale'+str(seconds)})
    report={'schema':'ark-sim/chapter06-cold-source-binding/v1','numeric_sources_sha256':sha(numeric),'native_reference':n['native_reference'],'module_sha256':sha(model),'bindings':bindings,'all_ten_source_values_bound':len(bindings)==10,'target_predicate':'e2c_frozen_atkscale BSON ON_CALCULATE_DAMAGE TARGET FROZEN; typed flag16 consumer','complete_enemy_modules':False,'whole_stage_executed':False,'independent_reviewed':False,'client_verified':False,'builder_sha256':sha(Path(__file__))}
    p=OUT/'source.binding.json';p.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({'binding_sha256':sha(p),'bound':len(bindings)}))
if __name__=='__main__':main()
