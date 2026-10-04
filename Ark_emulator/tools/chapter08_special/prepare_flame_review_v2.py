"""Preserve positivev1 artifacts, correct controlled pipeline implementation kind only."""
from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'review_flame_v1.py').read_text().replace('flame_independent_v1','flame_independent_v2')
s=s.replace("'type':'expression','expression':\"{'accepted':inputs.effect.settlement.accepted,'amount':inputs.effect.settlement.amount*.5,'allocations':[],'events':[]}\"", "'type':'graph','nodes':[{'id':'result','expression':\"{'accepted':inputs.effect.settlement.accepted,'amount':inputs.effect.settlement.amount*.5,'allocations':[],'events':[]}\"}],'output':'nodes.result'")
s=s.replace("'type':'expression','expression':\"inputs.effect.settlement if ('consider_unhurtable' in inputs.effect.parameters and inputs.effect.parameters.consider_unhurtable == False) else {'accepted':False,'amount':0,'allocations':[],'events':[]}\"", "'type':'graph','nodes':[{'id':'result','expression':\"inputs.effect.settlement if ('consider_unhurtable' in inputs.effect.parameters and inputs.effect.parameters.consider_unhurtable == False) else {'accepted':False,'amount':0,'allocations':[],'events':[]}\"}],'output':'nodes.result'")
(HERE/'review_flame_v2.py').write_text(s,encoding='utf-8',newline='')
