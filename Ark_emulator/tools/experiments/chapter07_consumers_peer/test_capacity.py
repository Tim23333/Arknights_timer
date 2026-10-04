import json
from copy import deepcopy
from tools.experiments.chapter07_consumers_peer.test_cards_warmed import fixed_package,deploy,MINE_ID
from tools.experiments.chapter07_consumers_peer.common import *
def test_cards_preserve_real_scenario_zero_capacity_gate():
 p=fixed_package('capacity_zero');p['scenarioDraft']['parameters']={'deploy_capacity':0};src=json.loads(MINE.read_text(encoding='utf8'));fake=deepcopy(src['entities'][0]);fake['id']='unit/peer/one_slot';fake['components']['deployable']['capacity']=1;p['entities'].append(fake);p['scenarioDraft']['cards']=[MINE_ID,'unit/peer/one_slot'];s=create(p,[MINE]);s.submit(deploy('one_slot','unit/peer/one_slot'),at=0);s.submit(deploy(),at=1);s.advance(2);capture(s,'real_zero_capacity');assert len(events(s,'command.rejected'))==len(events(s,'command.accepted'))==1 and s.ctx.resources.current('system/battle','dp')==95 and s.ctx.resources.current('system/battle','stock_ch7_mine')==14
