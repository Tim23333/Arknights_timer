import json
from pathlib import Path
from tools.experiments.chapter07_consumers_peer.common import *
MINE_ID='unit/ch7/predefined/mine/level1'
NATIVE=BASE/'chapter07_stage_models/level_main_07-15.native_draft.v1.json'
def test_native_mine_card_deploy_expected_with_actual_fixed12_roster():
 native=json.loads(NATIVE.read_text(encoding='utf8'));p=package('fixed12_card');p['definitions']=native['definitions'];p['scenarioDraft']['roster']=native['scenarioDraft']['roster'];p['scenarioDraft']['dependencies']=[MINE_ID];p['scenarioDraft']['metadata']={'native_card_bindings':[{'definition':MINE_ID,'characterKey':'trap_012_mine','stock_resource':'stock_ch7_mine','source_stock':15}],'scope':'Controlled minimal card availability; actual fixed12 definitions preserved; not a native stage run'}
 p['scenarioDraft']['map']['tiles']=[{'tileKey':'tile_floor','buildableType':1,'heightType':0,'passableMask':1,'advancedBuildMask':1} for _ in range(49)];s=create(p,[MINE]);s.submit({'action':'deploy','definition':MINE_ID,'position':{'row':1,'col':1},'alias':'mine'},at=0);s.advance(1);capture(s,'native_card_fixed12')
 assert len(s.program.scenario['roster'])==12 and MINE_ID not in s.program.scenario['roster'];assert len(events(s,'command.accepted'))==1
