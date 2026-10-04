"""M70 source-backed intrinsic and control-contribution profile; no rebirth claim."""
import argparse,hashlib,json,re
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1]
PINS={'packages/campaign/chapter04_boss_plan/source.reference.json':'7ad2fb46b3e281711b6faf8b7a3bacfb9df6bc11ff32212a8439d8925d6893ec','packages/campaign/chapter04_boss/m61/rebirth.reference_model.json':'11f14fa086dc2906bb5318003a9b24880a62d570f4f87aff7a42e0fb40fa0a4b','packages/campaign/skills.chen.json':'04df7b6f7f40f43687c03b0186e02f4e0407ee566231f43b2455d2741719dde6'}
OUT=ROOT/'packages/campaign/chapter04_boss/m70/immunity.reference_model.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 for name,pin in PINS.items():
  if sha(ROOT/name)!=pin:raise ValueError('Source drift '+name)
 source=json.loads((ROOT/next(iter(PINS))).read_bytes());prior=json.loads((ROOT/'packages/campaign/chapter04_boss/m61/rebirth.reference_model.json').read_bytes());chen=json.loads((ROOT/'packages/campaign/skills.chen.json').read_bytes())
 dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';dump_pin='18c43dde9466317c45a786a0e4fa35cd8894d128592adda4394704bf99ea477b'
 if sha(dump)!=dump_pin:raise ValueError('Source enum dump drift')
 text=dump.read_text(encoding='utf8');names={'stunImmune':('STUNNED',0),'silenceImmune':('SILENCED',12),'frozenImmune':('FROZEN',16),'levitateImmune':('LEVITATE',25)}
 for name,index in names.values():
  if not re.search(r'\b'+name+r'\s*=\s*'+str(index)+r'\s*;',text):raise ValueError('Source enum '+name)
 attrs=source['native_enemy']['resolved']['attributes'];indices=[index for field,(name,index) in names.items() if attrs[field] is True]
 assert indices==[0,12,16,25]
 passive=source['boss_components']['-1970201548829853972']['raw']['_buffs'][0];assert passive['buffKey']=='frstar_c' and passive['attributes']['abnormalComboImmunes']==[0] and passive['isSilenceable']==0
 raw=chen['manifest']['metadata']['native_skill_prefab']['components'][1]['fields']['_activeBuffs'][0];assert raw['attributes']['abnormalFlags']==[0]
 unit=deepcopy(prior['entities'][0]);unit['components'].pop('rebirth');unit['components']['selection_state']['abnormal_immunes']=indices;unit['components']['buffs']={'initial':['buff/ch4/frstar/initial_sleep_immune']}
 unit['metadata']['scope']='Exact intrinsic four immunity operands and initial sleep-combo immunity. Phase switch explicitly modeled by removing initial Buff; no rebirth/whole Boss claim.'
 stun=deepcopy(chen['buffs'][0]);assert stun['duration_seconds']==1.5;stun['selection_flags']={'abnormal_flags':[0]};stun['control_rule']='rule/m70/stun_control'
 return {'schemaVersion':2,'manifest':{'id':'package/ch4/frstar/immunity/reference','requires':['preset/ark_standard'],'metadata':{'source_locks':{**PINS,str(dump.relative_to(ROOT.parent)):{'root':'parent','sha256':dump_pin}},'builder_sha256':sha(Path(__file__)),'intrinsic_flag_map':names,'source_initial_sleep_buff':passive,'source_chen_stun_buff':raw,'reference_sources':source['reference_sources'],'profile':'Intrinsic abnormal immunes subtract flags; combo immunity subtracts combos independently. Persist applied control Buff, gate control/interrupt by effective status. ATK/other contributions remain unless separately active_rule gated. First-phase sleep immunity is a Buff removed at phase transition; true rebirth callback integration deferred.','model_gaps':['Actual M61/M74 rebirth integration is not in this M68-parent phase demo','Status application duration resistance and unmodeled native dispatch remain configurable feedback items','Whole FrostNova skills/blackice not included'],'client_verified':False,'formal_approved':False}},'entities':[unit],'buffs':[{'id':'buff/ch4/frstar/initial_sleep_immune','kind':'buff','selection_flags':{'abnormal_combo_immunes':[0]}},stun,{'id':'buff/m70/sleep','kind':'buff','control_rule':'rule/m70/sleep_control','selection_flags':{'abnormal_combos':[0]},'control':{'move':False,'attack':False,'abilities':False,'block':False,'interrupt':True}}],'rules':[{'id':'rule/m70/stun_control','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_flags'}},{'id':'rule/m70/sleep_control','kind':'rule','contract':'buff.applicability','implementation':{'type':'expression','expression':'0 in inputs.status.abnormal_combos'}}]}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();raw=(json.dumps(build(),ensure_ascii=False,indent=2)+'\n').encode('utf8');OUT.parent.mkdir(parents=True,exist_ok=True)
 if a.check:
  if OUT.read_bytes()!=raw:raise ValueError('Source immunity model stale')
 else:OUT.write_bytes(raw)
 print(json.dumps({'path':str(OUT),'sha256':sha(OUT),'client_verified':False,'rebirth_integrated':False}))
