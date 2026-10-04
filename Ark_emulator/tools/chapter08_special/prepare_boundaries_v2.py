"""Source goldens unchanged; explicit fixture refund/life objective and actual exit event domain."""
from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'test_boundaries_v1.py').read_text()
s=s.replace("p=package('empace',True);unit=p['entities'][1]['id'];", "p=package('empace',True);p['entities'][1]['components']['deployable']['refund_ratio']=0;unit=p['entities'][1]['id'];")
s=s.replace("p['scenarioDraft']['resources']['life']={'initial':3,'capacity':3};", "p['scenarioDraft']['resources']['life']={'initial':3,'capacity':3};p['scenarioDraft']['objectives']={'life_resource':'life'};")
s=s.replace("len([e for e in s.session.events if e['type']=='entity.leaked'])==1", "s.ctx.state()['leaks']==1")
(HERE/'test_boundaries_v2.py').write_text(s,encoding='utf-8',newline='')
s=(HERE/'verify_author_v3.py').read_text().replace('test_author_v3.py','test_boundaries_v2.py').replace('author.v3.tests.json','boundaries.v2.tests.json')
(HERE/'verify_boundaries_v2.py').write_text(s,encoding='utf-8',newline='')
