"""Fresh final V8/v11 execution, unchanged source mathematics and fixed native roster."""
from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'review_dynamic_burn_v3.py').read_text().replace('campaign_buff_lifetime_v5_candidate','campaign_buff_lifetime_v8_candidate').replace('dragon_fire.module.v10.dynamic.json','dragon_fire.module.v11.dynamic.json').replace('dynamic_burn_independent_v3','dynamic_burn_independent_v4').replace('df80b2ba4026c41d0dc0b4283da587dc1cffa3e89ffc46df2b6d6fa44686f9a0','be1b6be85a29b84d31a7444f186212bf71a85b538edea781f8a54080cba91bb7')
(HERE/'review_dynamic_burn_v4.py').write_text(s,encoding='utf-8',newline='')
s=(HERE/'review_roster_burn_v3.py').read_text().replace('campaign_buff_lifetime_v5_candidate','campaign_buff_lifetime_v8_candidate').replace('dragon_fire.module.v10.dynamic.json','dragon_fire.module.v11.dynamic.json').replace('dynamic_roster_independent_v3','dynamic_roster_independent_v4')
(HERE/'review_roster_burn_v4.py').write_text(s,encoding='utf-8',newline='')
