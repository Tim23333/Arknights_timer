from ark_sim import Compiler,Engine
from tools.chapter07_boss.policies_v2 import providers as compatible_invul
from tools.experiments.chapter07_consumers_peer.common import *
from tools.experiments.chapter07_consumers_peer.test_ore import ore
def test_consider_unhurtable_false_bypasses_compatible_hook_keeps_other_multiplier():
 p=package('ore_hooks');ore(p);recipient(p,'a',(3,4));p['rules'].append({'id':'rule/peer/invul','kind':'rule','contract':'damage.pipeline','implementation':{'type':'provider','provider':'reference.ch7.patrt_invulnerability'}});p['buffs'].append({'id':'buff/peer/invul','kind':'buff','damage_hooks':[{'phase':'after','rule':'rule/peer/invul'}]});p['entities'][0]['components']['buffs']={'initial':['buff/peer/invul','buff/ch7/predefined/mine/vulnerable']}
 controller(p,[ability('ordinary_probe',[{'op':'damage','target':3,'damage_type':'true','scale':0,'additions':500}])]);p['entities'][-1]['components']['attributes']={'base':{'max_hp':100,'atk':17,'def':31,'mres':17}}
 INPUTS.append({'package':p,'modules':[str(ORE),str(MINE)]});reg={**registry(),**compatible_invul()};s=Engine.create(Compiler(providers=reg).compile(p,packages=[str(ORE),str(MINE)]),providers=reg,seed=70761);command(s,'ordinary_probe',21);s.advance(23);capture(s,'ore_compatible_hooks');hits=events(s,'damage.accepted');assert len(hits)==1 and hits[0]['time']==19 and hits[0]['payload']['amount']==750 and s.ctx.resources.current('a','hp')==8250
