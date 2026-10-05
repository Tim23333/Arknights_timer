from tools.chapter09_mandra_peer.common import *
results=[];facts={}
try:
 p=scene(near=True,lethal_player=True);s=proof(p,'047_resources_container_fix',[159],190);assert not s.ctx.alive('player');tokens=[e for e in s.session.world.entities() if e['definition_id']=='unit/ch9/mandra/sealed_ground'];assert len(tokens)==1;token=tokens[0];assert not token['components'].get('resources',{});assert s.ctx.get(token['id'],('ownership','owner'))==s.session.world.resolve('boss');facts['047']={'HP_not_fabricated':True,'empty_resources_normalized_by_initializer':True,'actual_owned_token':True};results.append({'case':'047_no_health_not_absent_container','passed':True})
except Exception as e:results.append({'case':'047_no_health_not_absent_container','passed':False,'error':str(e),'traceback':traceback.format_exc()})
try:
 p=scene();next(b for b in p['buffs'] if b['id']==RECOVERY)['on_remove'].append({'op':'apply_buff','target':'source','buff':'buff/peer/m/fault'});p['buffs'].append({'id':'buff/peer/m/fault','kind':'buff','effects':[{'op':'random','stream':'peer.mandra_fault','probability':1,'on_success':[{'op':'emit','event':'peer.before_mandra_fault'}]},{'op':'modify_resource','resource':'missing','amount':1}]});s=create(p);s.ctx.effects.execute('pillar',['boss'],{'op':'damage','damage_type':'true','scale':1});s.advance(1);assert any(b['definition']==RECOVERY for b in buffs(s));s.ctx.attributes.value('boss','def');before=s.checkpoint()
 try:s.ctx.effects.execute('boss',['boss'],{'op':'remove_buff','buff':RECOVERY})
 except ValueError as e:assert 'missing' in str(e);facts['latefault']={'actual_reason':str(e),'Recovery_really_present_before_remove':True}
 else:raise AssertionError('real late fault accepted')
 assert s.checkpoint()==before;assert not events(s,'peer.before_mandra_fault');assert s.session.random.samples==();results.append({'case':'actual_created_Recovery_remove_random_missing_exact_fullrollback','passed':True})
except Exception as e:results.append({'case':'actual_created_Recovery_remove_random_missing_exact_fullrollback','passed':False,'error':str(e),'traceback':traceback.format_exc()})
assert guard()==START;r={'core':CORE,'actual_exit':0 if all(x['passed'] for x in results) else 1,'results':results,'facts':facts,'artifacts':ART,'source_guard_equal':True,'initial_failures_preserved':True,'true_second_life_counter_unresolved':True};(OUT/'fixture_fixes.actual.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({'actual_exit':r['actual_exit'],'results':results}));raise SystemExit(r['actual_exit'])
