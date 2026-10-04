"""Development cache persistence/tamper/transaction tests; fresh V3 execution."""
import importlib.util,json,copy,hashlib,traceback
from pathlib import Path
spec=importlib.util.spec_from_file_location('own_v3',Path(__file__).with_name('review_v5.py'))
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
from ark_sim.contracts import digest,thaw
from ark_sim.tools.replay import replay
RESULTS=[]
def run(name,fn):
    try:fn();RESULTS.append({'case':name,'passed':True})
    except Exception as e:RESULTS.append({'case':name,'passed':False,'error':str(e),'traceback':traceback.format_exc()})
def cp(s):return json.loads(json.dumps(s.checkpoint(),allow_nan=False))
def fresh(time=0):
    s=p.sim(p.joint_data()[0]);s.session.advance(time);return s
def restore(s,checkpoint):return p.Engine.restore(s.program,checkpoint)
def record(s):
    a,b=p.refs(s);s.ctx.attributes.value(b,'magic_resistance');v=cp(s);assert v['attribute_cache']['entries'];return v
def roundtrip():
    for t in (0,7):
        s=fresh(t);p.ep(s,amount=19);v=record(s);r=restore(s,v);assert cp(s)==cp(r)
        s.session.advance(8);r.session.advance(8);assert cp(s)==cp(r)
def no_query():
    s=fresh(5);p.ep(s,amount=19);r=restore(s,cp(s));s.session.advance(7);r.session.advance(7);assert cp(s)==cp(r)
def no_event_checkpoint():
    s=fresh();record(s);before=s.session.checkpoint();before_full=cp(s);x=s.checkpoint();assert s.session.checkpoint()==before;assert x['attribute_cache']==s.checkpoint()['attribute_cache']
def tamper():
    s=fresh();v=record(s)
    for key,value in [('value',777),('source_event_id',1),('view_version',777),('view_digest','bad'),('effect',{'rules':{'attributes.effective':'rule/missing'}})]:
        q=copy.deepcopy(v);row=q['attribute_cache']['entries'][0];row[key]=value
        row['record_digest']=digest({k:x for k,x in row.items() if k!='record_digest'})
        try:restore(s,q)
        except (ValueError,KeyError):pass
        else:raise AssertionError('tampered cache accepted '+key)
    for key,value in [('schema','bad'),('time',1),('rules_fingerprint','bad')]:
        q=copy.deepcopy(v);q['attribute_cache'][key]=value
        try:restore(s,q)
        except ValueError:pass
        else:raise AssertionError('tampered cache header accepted '+key)
def source_scope():
    s=fresh();a,b=p.refs(s);effects=[{'metadata':{'source_context':'left'}},{'metadata':{'source_context':'right'}}]
    for e in effects:assert s.ctx.attributes.value(b,'magic_resistance',effect=e)==55
    v=cp(s);rows=[x for x in v['attribute_cache']['entries'] if x['effect']];assert len(rows)==2 and rows[0]['source_event_id']!=rows[1]['source_event_id'];r=restore(s,v)
    for e in effects:
        s.ctx.attributes.value(b,'magic_resistance',effect=e);r.ctx.attributes.value(b,'magic_resistance',effect=e)
    assert cp(s)==cp(r)
    q=copy.deepcopy(v);left,right=[x for x in q['attribute_cache']['entries'] if x['effect']];left['source_event_id']=right['source_event_id'];left['event_digest']=right['event_digest'];left['record_digest']=digest({k:x for k,x in left.items() if k!='record_digest'})
    try:restore(s,q)
    except ValueError:pass
    else:raise AssertionError('cross-context cause borrowed')
def owner_generation():
    s=fresh();v=record(s);q=copy.deepcopy(v);owner=p.refs(s)[1];world=q['kernel']['world'];entity=next(e for e in world['entities'] if e['id']==owner);entity['components']['runtime']['lifecycle_generation']=1
    try:restore(s,q)
    except ValueError:pass
    else:raise AssertionError('old cache borrowed by changed lifecycle')
def live_invalidation():
    s=fresh();a,b=p.refs(s);s.ctx.attributes.value(b,'magic_resistance');s.ctx.set(b,('attributes','base','magic_resistance'),66);assert s.ctx.attributes.value(b,'magic_resistance')==66
    v=cp(s);assert all(x['value']==66 for x in v['attribute_cache']['entries'] if x['attribute']=='magic_resistance');r=restore(s,v);s.ctx.attributes.value(b,'magic_resistance');r.ctx.attributes.value(b,'magic_resistance');assert cp(s)==cp(r)
def nested_rollback():
    s=fresh();a,b=p.refs(s);s.ctx.attributes.value(b,'magic_resistance');before=s.session.checkpoint();before_full=cp(s)
    try:
        with s.session.atomic():
            s.ctx.set(b,('attributes','base','magic_resistance'),81);s.ctx.attributes.value(b,'magic_resistance')
            with s.session.atomic():
                s.ctx.set(b,('attributes','base','magic_resistance'),99);s.ctx.attributes.value(b,'magic_resistance');raise ValueError('late fault')
    except ValueError:pass
    assert s.session.checkpoint()==before
    assert cp(s)==before_full;assert s.ctx.attributes.value(b,'magic_resistance')==55
    r=restore(s,cp(s));s.ctx.attributes.value(b,'magic_resistance');r.ctx.attributes.value(b,'magic_resistance');assert cp(s)==cp(r)
def time_invalidation():
    s=fresh();a,b=p.refs(s);record(s);s.session.advance(1);assert cp(s)['attribute_cache']['entries']==[];s.ctx.attributes.value(b,'magic_resistance');v=cp(s);assert v['attribute_cache']['time']==1
    for row in v['attribute_cache']['entries']:assert s.session.events[row['source_event_id']-1]['time']==1
def old_optional():
    s=fresh();v=record(s);v.pop('attribute_cache');r=restore(s,v);assert r.ctx.attributes.value(p.refs(r)[1],'magic_resistance')==55
def history_no_identity_borrow():
    s=fresh();a,b=p.refs(s);snapshot=s.ctx.capture_view(b);s.ctx.attributes.value(b,'magic_resistance',snapshot=snapshot);assert all(x['attribute']!='magic_resistance' for x in cp(s)['attribute_cache']['entries'])
def public_replay():
    d=p.joint_data()[0];d['entities'][0]['components']['abilities']=['peer/public_ep'];d['selectors']=[{'id':'peer/targets','kind':'selector','region':{'type':'all'},'filters':[{'tag':'enemy'},{'state':'alive'}],'limit':1}]
    d['abilities']=[{'id':'peer/public_ep','kind':'ability','activation':{'mode':'manual'},'selector':'peer/targets','timeline':[{'at':0,'effect':{'op':'elemental_damage','element':'alpha','amount':19}}]}]
    s=p.sim(d);s.submit({'action':'skill','source':'src','ability':'peer/public_ep'},at=0);s.session.advance(5);r=replay(s.program,s.export_replay());assert s.checkpoint()==r.checkpoint()
def main():
    assert p.implementation_digest()==p.EXPECTED
    for n,f in [('time0_nonzero_fire_pending_sp_cpp',roundtrip),('no_query_existing_case',no_query),('checkpoint_no_events_or_world_mutation',no_event_checkpoint),('tamper_value_event_version_rule_time_fingerprint',tamper),('same_value_different_scopes_no_cause_borrow',source_scope),('owner_lifecycle_no_old_cache',owner_generation),('live_world_invalidation',live_invalidation),('nested_transaction_rollback',nested_rollback),('clock_boundary_invalidation',time_invalidation),('optional_old_cache_extension_safe_miss',old_optional),('historical_snapshot_not_live_identity',history_no_identity_borrow),('public_commands_export_replay_head',public_replay)]:run(n,f)
    out=p.OUT/'cache.tests.v5.json';out.parent.mkdir(parents=True,exist_ok=True);report={'core':p.implementation_digest(),'actual_exit':0 if all(x['passed'] for x in RESULTS) else 1,'tests':RESULTS,'cpp_claim':'low-level effect/query fixtures test checkpoint continuation only','head_claim':'exportReplay head tested separately using public commands; debug queries are not automatically recorded'};out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False));return report['actual_exit']
if __name__=='__main__':raise SystemExit(main())
