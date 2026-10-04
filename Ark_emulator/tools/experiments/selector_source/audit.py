import json,re,hashlib
from pathlib import Path
import UnityPy
ROOT=Path(__file__).resolve().parents[3];DUMP=ROOT.parent/'Ark_data/dump.cs';text=DUMP.read_text(encoding='utf8');sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
names=['AbnormalFlag','AbnormalCombo','MotionMask','SideType','SideTypeIndex','EntityCategory','ProfessionCategory','UnitTypeMask'];enums={}
for name in names:
 match=re.search(r'public enum '+name+r' [^\n]*\n\{(.*?)\n\}',text,re.S);assert match;enums[name]={'values':{n:int(v) for n,v in re.findall(r'public const '+name+r' (\w+) = (-?\d+);',match[1])},'declaration_line':text[:match.start()].count('\n')+1,'text':match[0]}
assert enums['AbnormalFlag']['values']['TELEPORTED']==44 and enums['AbnormalFlag']['values']['SKILL_NOT_ACTIVATABLE']==24 and enums['AbnormalFlag']['values']['E_NUM']==46 and enums['AbnormalCombo']['values']['E_NUM']==2
start=text.index('public class AdvancedSelector :');end=text.index('// Methods',start);decl=text[start:end];assert 'public AbnormalFlag _abnormalFlag;' in decl and 'public AbnormalCombo _abnormalCombo;' in decl
source=json.loads((ROOT/'packages/campaign/chapter01_sources/native.reference.json').read_bytes());cache={};selectors=[]
for cid in ['enemy_1028_mocock','enemy_1028_mocock_2','enemy_1504_cqbw']:
 enemy=source['enemies'][cid];record=enemy['prefab']['source'];path=ROOT.parent/record['path'];assert sha(path)==record['sha256']
 if path not in cache:cache[path]={o.path_id:o for o in UnityPy.load(str(path)).objects}
 for pid,c in enemy['prefab']['components'].items():
  if c['native_class'] not in ['AdvancedSelector','SecondaryFilterAdvancedSelector']:continue
  raw=cache[path][int(pid)].read_typetree();assert raw==c['raw'];assert raw['_ignoreTargetFree']==0 and raw['_onlyIgnoreSomeOfTargetFreeCase']==0 and raw['_excludeSomeAbnormalFlags']==0 and raw['_needProfessionMask']==0
  selectors.append({'owner':cid,'actual_component_path_id':int(pid),'source':record,'actual_native_class':c['native_class'],'raw':raw,'inactive_enum_values':{'abnormalFlag':raw['_abnormalFlag'],'abnormalCombo':raw['_abnormalCombo'],'excludeAbnormalFlag':raw['_excludeAbnormalFlag']},'active_model_requirements':['respect_target_free','respect_camouflage_unless_source_capability','relative_side','motion_mask','entity_category']})
# Native Buff arrays are enum-index lists, not integers already containing masks.
flag_sources=[]
for relative in ['packages/campaign/support_tokens.reference.json','packages/campaign/chapter01_devices/emp.source.json']:
 d=json.loads((ROOT/relative).read_bytes())
 def scan(value,pointer=''):
  if isinstance(value,dict):
   for key,v in value.items():
    if key in ('abnormalFlags','abnormalCombos') and v:flag_sources.append({'path':relative,'source_sha256':sha(ROOT/relative),'pointer':pointer+'/'+key,'values':v,'names':[next(n for n,num in enums['AbnormalFlag' if key=='abnormalFlags' else 'AbnormalCombo']['values'].items() if num==i) for i in v]})
    scan(v,pointer+'/'+key)
  elif isinstance(value,list):
   for i,v in enumerate(value):scan(v,pointer+'/'+str(i))
 scan(d)
result={'schema':'ark-sim/advanced-selector-source-audit/v1','passed':True,'dump_sha256':sha(DUMP),'enum_declarations':enums,'advanced_selector_fields':decl,'actual_selectors':selectors,'native_buff_flag_sources':flag_sources,'method_body_scope':'Entity.get_isTargetFree/isTargetFreeWithImmuneFlag/canSelectCamouflageTarget and Selector.ValidateTarget are empty dump declarations, not recovered algorithms','disabled_values_not_filters':True,'source_gaps':['No current fixed12/token/EMP recorded sample establishes target-free or camouflage aggregate getter body; propose explicit modeled flag/reason state instead of inferring from stale enum slots'],'formal_approval':False,'tests':[{'path':str(Path(__file__).relative_to(ROOT)).replace('\\','/'),'source_sha256':sha(__file__),'result':'passed'}]}
out=ROOT/'validation/campaign/advanced_selector_source_audit.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':True,'actual_selectors':len(selectors),'buff_flag_sources':len(flag_sources)}))
