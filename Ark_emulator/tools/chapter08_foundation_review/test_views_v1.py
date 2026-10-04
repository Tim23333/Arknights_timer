import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT.parent/'unpack_work/campaign_campaign_foundation_v5_candidate'));sys.path.insert(1,str(ROOT))
from ark_sim.kernel.world import World
import pytest
def test_metadata_string_subclass_cannot_invoke_deepcopy_in_trusted_fork():
 class Hostile(str):
  def __deepcopy__(self,memo):raise AssertionError('user deepcopy callback invoked')
 w=World();n=w.create(Hostile('entity/unicode/测试'),{'nested':{'text':'𝄞中文','number':-0.0,'none':None}},tags=[Hostile('先'),Hostile('后')],alias=Hostile('影'));f=w._fork_validated();assert type(f._entities[n]['definition_id']) is str and all(type(x) is str for x in f._entities[n]['tags']) and all(type(x) is str for x in f._aliases);assert f.snapshot()==w.snapshot();w._adopt_validated(f,preserve_views=False);assert w.resolve('影')==n

def test_component_subtree_byte_values_and_key_order_immutable_oldview_unchanged():
 w=World();n=w.create('entity/order',{'root':{'second':[{'𝄞':'中文','x':.125}], 'first':True,'third':None}},alias='q');leaf=w.component_view(n,('root',));assert list(leaf)==['second','first','third'];f=w._fork_validated();f.set(n,('root','second',0,'x'),.375);w._adopt_validated(f,preserve_views=True);assert leaf['second'][0]['x']==.125 and w.component_view(n,('root',))['second'][0]['x']==.375;assert list(w.component_view(n,('root',)))==['second','first','third']
 with pytest.raises(TypeError):leaf['second'][0]['x']=1
