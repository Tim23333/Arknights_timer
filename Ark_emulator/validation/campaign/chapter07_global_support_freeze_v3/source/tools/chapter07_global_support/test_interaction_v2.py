"""Exact unlike source .1/+100 commander and .2/+200 Patriot, common marker once."""
import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_finish_timeline_wave_v4_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim import Compiler,Engine
from tools.chapter07_global_support.test_source_v2 import package,MARKER,ATTRIBUTE,child
def test_Patriot_and_commander_different_source_fields_add_and_marker_shared():
 p=package();patrt=json.loads((ROOT/'validation/campaign/shared_aura_patrt_self_source_v10/input.json').read_bytes());ids={}
 for kind in ('entities','abilities','selectors','behaviors','rules','buffs'):
  for d in p.get(kind,[]):ids[d['id']]=d
  for d in patrt.get(kind,[]):
   if d['id'] in ids:assert ids[d['id']]==d,'Real content definition conflict: '+d['id']
   else:p.setdefault(kind,[]).append(deepcopy(d));ids[d['id']]=d
 p['scenarioDraft']['map']={'rows':5,'cols':7};p['scenarioDraft']['initialEntities'].append({'definition':patrt['entities'][0]['id'],'instanceAlias':'patriot','position':{'row':4,'col':5}});s=Engine.create(Compiler().compile(p));assert s.ctx.attributes.value('receiver','atk')==130 and s.ctx.attributes.value('receiver','def')==350;assert len(child(s,ATTRIBUTE))==1;patrtattrs=[i for i in s.ctx.entity('receiver')['components']['buffs']['instances'] if i['definition'].endswith('/strength')];assert len(patrtattrs)==1;marker=child(s,MARKER);assert len(marker)==1 and len(marker[0]['aura_leases'])==2;s.ctx.lifecycle.retire('commander1','withdrawn');assert s.ctx.attributes.value('receiver','atk')==120 and s.ctx.attributes.value('receiver','def')==250 and len(child(s,MARKER))==1;s.ctx.lifecycle.retire('patriot','withdrawn');assert s.ctx.attributes.value('receiver','atk')==100 and not child(s,MARKER)
