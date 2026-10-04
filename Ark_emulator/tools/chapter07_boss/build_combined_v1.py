"""New source identity for exact shared Aura + waiting action + spear inputs."""
from pathlib import Path
import json
from tools.chapter07_boss.build_mechanism_v1 import ROOT,OUT,UID,MARKER,sha
from tools.chapter07_boss.build_waiting_v1 import TIMER,STATS,IMMO
def main():
 spear=OUT/'mechanism.v5.json';waiting=OUT/'waiting.mechanism.v2.json';p=json.loads(spear.read_bytes());w=json.loads(waiting.read_bytes());needed=[d for d in w['rules'] if d['id'].endswith('/waiting_stats_active')];p['rules']+=needed
 for b in w['buffs']:
  if b['id'] in [TIMER,STATS]:p['buffs'].append(b)
 c=p['entities'][0]['components'];wc=w['entities'][0]['components'];c['rebirth']['waiting_actions']=wc['rebirth']['waiting_actions'];c['rebirth']['retain_buffs'].append(TIMER);c['rebirth']['on_begin'] += [e for e in wc['rebirth']['on_begin'] if e.get('buff') in [TIMER,STATS]];c['rebirth']['on_finish'].append({'op':'remove_buff','target':'source','buff':STATS})
 parent='buff/'+UID+'/marker_parent';aura='selector/'+UID+'/allies';policy={'mode':'shared','identity':['definition','target'],'source_binding':'oldest_live_lease','external_child_collision':'reject','owner_activity':'active_or_rebirth_waiting'}
 for b in p['buffs']:
  if b['id']=='buff/'+UID+'/strength':b['stacking']={'mode':'refresh','max_stacks':1,'identity':['definition','target']}
  if b.get('aura'):b['aura']['lease_policy']=policy
  if b['id']=='buff/ch7/source/ore_immune':b.pop('metadata',None)
 p['buffs'] += [{'id':MARKER,'kind':'buff','metadata':{'source_role':'External source marker identity; emitter separate, no invented stat buff'}},{'id':parent,'kind':'buff','aura':{'selector':aura,'buff':MARKER,'lease_policy':policy}}];c['buffs']['initial'].append(parent);c['rebirth']['retain_buffs'].append(parent)
 # Shared parent survives the finite waiting generation; do not refresh it.
 for hook in ['on_begin','on_finish']:c['rebirth'][hook]=[e for e in c['rebirth'][hook] if e.get('buff')!='buff/'+UID+'/strength_parent']
 p['manifest']['id']='package/ch7/patrt/combined_source_mechanisms_v1';meta=p['manifest']['metadata'];meta['builder_sha256']=sha(Path(__file__));meta['source_locks'][str(spear.relative_to(ROOT))]=sha(spear);meta['source_locks'][str(waiting.relative_to(ROOT))]=sha(waiting);meta['status']='combined_source_mechanisms_wave_release_and_full_ore_integration_pending';meta['single_emitter_probe_adapter']='Removed prototypeindependent child; sourceattrs/marker useexactnonstacksharedleasedchild, realHP0 waiting allowed onlyactualretainedparent/generation';meta['unconsumed_required_mechanisms']=['ReleaseWave literalcurrentwave finish','Rootore/mine fullsourceintegration andnative stage/control joins'];meta['combined_expected_values_note']='Calculate actual currentownerATK after leases/modifiers; do not claim2240 untilactualproof. CurrentfixedBB .2Strength+.2Reborning implies2240 if bothcontribute.';path=OUT/'combined.mechanism.v1.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(path),'stage_export_allowed':False}))
if __name__=='__main__':main()
