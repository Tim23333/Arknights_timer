"""Same source math/public cases with new immutable V5/v10 execution identity."""
from pathlib import Path
import json
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
module=ROOT/'packages/campaign/chapter08_consumers/boss/dragon_fire.module.v10.dynamic.json'
core=json.loads(module.read_bytes())['manifest']['metadata']['required_runtime']
s=(HERE/'review_dynamic_burn_v2.py').read_text().replace('campaign_buff_lifetime_v3_candidate','campaign_buff_lifetime_v5_candidate').replace('dragon_fire.module.v7.dynamic.json','dragon_fire.module.v10.dynamic.json').replace('dynamic_burn_independent_v2','dynamic_burn_independent_v3').replace('da6ba0da3a469768b254ad89585b969f8ed761cb62f0c3eddfce840b854ff19c',core)
(HERE/'review_dynamic_burn_v3.py').write_text(s,encoding='utf-8',newline='')
s=(HERE/'review_roster_burn_v2.py').read_text().replace('campaign_buff_lifetime_v3_candidate','campaign_buff_lifetime_v5_candidate').replace('dragon_fire.module.v7.dynamic.json','dragon_fire.module.v10.dynamic.json').replace('dynamic_roster_independent_v2','dynamic_roster_independent_v3')
(HERE/'review_roster_burn_v3.py').write_text(s,encoding='utf-8',newline='')
