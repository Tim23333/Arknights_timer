"""New exact-assertion joint identity inputs; old single-candidate reports remain separate."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DIR=ROOT/'tools/chapter06_environment_consumer';CORE='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'
def write(name,s):
 p=DIR/name;assert not p.exists();p.write_text(s,encoding='utf8',newline='')
s=(DIR/'test_declared_static_tile_v2.py').read_text().replace('campaign_declared_static_tile_v1_candidate','campaign_chapter06_static_selfremove_v1_candidate');write('test_joint_static_v1.py',s)
s=(DIR/'probe_route_v7.py').read_text().replace('campaign_declared_static_tile_v1_candidate','campaign_chapter06_static_selfremove_v1_candidate').replace('chapter06_environment_v7','chapter06_environment_joint_v1').replace('8c58a6b704da11c42540357f37331ef604ac737056c1baf40ca7b14e44578924',CORE);write('probe_joint_route_v1.py',s)
s=(DIR/'verify_candidate_v1.py').read_text().replace('campaign_declared_static_tile_v1_candidate','campaign_chapter06_static_selfremove_v1_candidate').replace('chapter06_environment_candidate_v1','chapter06_static_selfremove_v1').replace('8c58a6b704da11c42540357f37331ef604ac737056c1baf40ca7b14e44578924',CORE).replace('test_declared_static_tile_v2.py','test_joint_static_v1.py');write('verify_joint_v1.py',s)
print('Created joint currentcore source probes; behavioral assertions unchanged')
