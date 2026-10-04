from types import SimpleNamespace
from tools.chapter07_ranged_consumers.mortar_box_v2 import mortar_box
class Context(dict):
 def calculate(self,name,inputs,rule_id):
  assert name=='targeting.eligibility' and rule_id=='rule/test/eligibility';s=inputs['selection_states']['candidate'];return SimpleNamespace(value={'accepted':s['eligible'],'reason':'test literal'})
def test_continuous_box_includes_corner_and_exact_edge_not_circle():
 candidates=[{'id':i,'components':{'spatial':{'position':{'row':r,'col':c}}}} for i,r,c in [(2,1.5,1.5),(3,1.50000001,0),(4,0,-1.5),(5,-1.5,-1.5),(6,0,0)]];ctx=Context(source={'id':1},area_selection_states={'source':{'eligible':True},'candidates':{str(i):{'eligible':i!=6} for i in range(2,7)}});assert mortar_box({'center_position':{'row':0,'col':0},'candidates':candidates,'parameters':{}},{'half_extent':1.5,'eligibility':{'rule':'rule/test/eligibility','parameters':{}}},ctx)==[2,4,5]
def test_missing_projection_rejected_not_raw_component_default():
 try:mortar_box({'center_position':{'row':0,'col':0},'candidates':[],'parameters':{}},{'half_extent':1.5},Context(source={'id':1}))
 except KeyError as e:assert e.args==('area_selection_states',)
 else:raise AssertionError('projection required')
