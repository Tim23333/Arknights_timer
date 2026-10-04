"""Independent source-bound HP ledger and one-area-per-burst stream audit.

This deliberately covers the fixed native story configuration: static initial
health, default health bounds and the exact no-source blood protocol. Unknown
custom bounds, growth, rebirth or dynamic base rewrites must not be certified.
"""
from collections import Counter,defaultdict
import hashlib,json,math
from pathlib import Path


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Strict finite source number required')
    return value


def audit(events,package):
    defs={d['id']:d for d in package['definitions']};actors={};hp={};pending={};prebirth={};counts=Counter();failures=[]
    starts=[];areas=defaultdict(list);hits=defaultdict(list);blood=[]
    boss=next(d for d in defs.values() if d.get('metadata',{}).get('native_variant_id','').startswith('enemy_1510_frstar2_s@'))
    burst=next(a for a in defs.values() if a['kind']=='ability' and a['id']==boss['components']['abilities'][0])
    if not burst['id'].endswith('/burst'):burst=next(a for a in defs.values() if a['kind']=='ability' and a['id'].endswith('/burst'))
    area=burst['timeline'][0]['effect'];assert area['op']=='area' and area.get('target') in ('self','source')
    buff=next(d for d in defs.values() if d['kind']=='buff' and any(e.get('op')=='no_source_damage' for e in d.get('effects',[])))
    protocol=next(e for e in buff['effects'] if e['op']=='no_source_damage');fixed=number(protocol['fixed_amount']);assert fixed==2000 and buff['interval_seconds']==1
    def fail(event,field,want,actual):failures.append({'event':event.get('id'),'time':event.get('time'),'field':field,'expected':want,'actual':actual})
    for e in events:
        counts['events']+=1;v=e.get('payload',{});kind=e['type'];time=e['time']
        if kind in ('entity.created','entity.registered'):
            ident=v['definition'];ref=v['target']
            if type(ref) is not int or ident not in defs:raise ValueError('Exact declared birth required')
            if ref in actors:
                if actors[ref]!=ident:fail(e,'actor_definition',actors[ref],ident)
                continue
            actors[ref]=ident;resource=defs[ident]['components'].get('resources',{}).get('hp')
            if resource:
                if resource.get('bounds_rule') or resource.get('capacity_rule'):raise ValueError('Custom source health initialization is outside this audit')
                hp[ref]=number(resource['initial']);counts['source_initial_hp']+=1
                for early in prebirth.pop(ref,[]):
                    if number(early['payload']['value'])!=hp[ref]:fail(early,'prebirth initial zero clip',hp[ref],early['payload']['value'])
                    counts['source_prebirth_zero_clip_checked']+=1
        if kind=='resource.changed' and v.get('resource')=='hp':
            ref=v['target']
            if ref not in hp:
                # Native initialization may report a zero capacity adjustment
                # before announcing the same newly allocated actor. Certify it
                # only after its actual source identity appears in this stream.
                if number(v['delta'])!=0:raise ValueError('Nonzero HP mutation before declared actor birth is outside this audit')
                prebirth.setdefault(ref,[]).append(e);continue
            previous=hp[ref];delta=number(v['delta']);value=number(v['value'])
            if value!=previous+delta:fail(e,'HP before+delta',previous+delta,value)
            if value<0:fail(e,'nonnegative HP',0,value)
            hp[ref]=value;pending[(v.get('source'),ref,time)]=(max(-delta,0),previous)
            counts['hp_transition_checked']+=1
        if kind=='damage.accepted':
            key=(v.get('source'),v['target'],time);row=pending.pop(key,None)
            if row is None:fail(e,'actual health delta','matching actual HP change',None)
            elif number(v['amount'])!=row[0]:fail(e,'damage vs HP loss',row[0],v['amount'])
            counts['damage_hp_loss_checked']+=1
            if v.get('source_policy')=='none':
                blood.append(e)
                for key in ('attack_type','damage_without_modify','ignore_for_sp','environmental','node_is_env_damage','env_blackboard_injected'):
                    if type(v.get(key)) is not type(protocol[key]) or v.get(key)!=protocol[key]:fail(e,key,protocol[key],v.get(key))
                if v.get('source') is not None:fail(e,'actor-free source',None,v.get('source'))
                for key in ('pipeline_amount','settlement_amount'):
                    if number(v[key])!=fixed:fail(e,key,fixed,v[key])
                if row is not None and number(v['amount'])!=min(fixed,row[1]):fail(e,'blood source clip',min(fixed,row[1]),v['amount'])
                if time%30:fail(e,'blood cadence',30,time)
                origin=v['origin']['buff_timer']
                if origin['owner']!=v['target'] or origin['definition']!=buff['id']:fail(e,'blood owned origin',buff['id'],origin)
                counts['blood_source_packet_checked']+=1
            elif v.get('ability')==burst['id']:hits[(v['source'],time)].append(e)
        if kind=='ability.started' and v.get('ability')==burst['id']:starts.append(e)
        if kind=='area.resolved' and actors.get(v['source'])==boss['id']:areas[(v['source'],time)].append(e)
    if prebirth:raise ValueError('Unbound prebirth HP observations')
    for start in starts:
        source=start['payload']['source'];time=start['time']+burst['timeline'][0]['at'];key=(source,time);packets=areas[key]
        if len(packets)!=1:fail(start,'one source-area per cast',1,len(packets));continue
        members=packets[0]['payload']['members'];actual=hits[key]
        if Counter(e['payload']['target'] for e in actual)!=Counter(members):fail(start,'one damage packet per actual member',members,[e['payload']['target'] for e in actual])
        counts['source_area_once_checked']+=1
    return {'passed':not failures,'counts':dict(counts),'final_hp':hp,'failures':failures,
        'scope':'Fixed story input source initial HP, HP transitions, damage actual health loss, PURE/BUFF blood amounts/origin/cadence and source-area multiplicity only.',
        'all_fields_independently_verified':False,'client_verified':False}


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--journal',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with a.journal.open(encoding='utf8') as f:report=audit((json.loads(line) for line in f),json.loads(a.package.read_bytes()))
    report.update(package_sha=hashlib.sha256(a.package.read_bytes()).hexdigest(),helper_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    assert not a.output.exists();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':report['passed'],'counts':report['counts'],'failures':report['failures'][:2]}));raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':main()
