"""Author input audit and bounded public plan; independent admission pending."""
import copy,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter06_review.stage_converter_v7 import exact
from tools.chapter06_review.stage_converter_v6 import route_ir,map_plan
from ark_sim import Compiler
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    folder=ROOT/'packages/campaign/chapter0_stage_models';plan=json.loads((ROOT/'packages/campaign/chapter0_source_prepare/source.plan.v3.json').read_bytes());roster=json.loads((ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json').read_bytes());rawdefs={d['id']:d for d in roster['definitions']};records=[]
    for name,row in plan['stages'].items():
        path=folder/(name+'.source.v2.json');p=json.loads(path.read_bytes());s=p['scenarioDraft'];native=row['native_document'];meta=p['manifest']['metadata'];assert exact(meta['native_document'],native) and exact(meta['native_action_records'],row['actions'])
        assert all(sha(k)==h for k,h in meta['source_locks'].items());assert exact(s['roster'],roster['manifest']['metadata']['roster']) and s['parameters']['deploy_capacity']==8
        assert s['resources']['dp']=={'initial':10,'capacity':99,'recovery_rate':1.0,'recovery':{'mode':'periodic','interval_seconds':1.0}} and s['resources']['life']=={'initial':99999,'capacity':99999}
        mp=map_plan(native);assert exact(s['map']['tiles'],mp['tiles']);defs={d['id']:d for d in p['definitions']}
        for uid in s['roster']:assert exact(defs[uid],rawdefs[uid])
        for uid,d in rawdefs.items():
            if d['kind']=='entity' and uid not in s['roster']:assert uid in defs and exact(defs[uid],d)
        born=0
        for wi,w in enumerate(s['timeline']['waves']):
            nw=native['waves'][wi];assert w['pre_delay_seconds']==nw['preDelay'] and w['post_delay_seconds']==nw['postDelay'] and w['max_wait_seconds']==nw['maxTimeWaitingForNextWave']
            for fi,f in enumerate(w['fragments']):
                nf=nw['fragments'][fi];assert f['pre_delay_seconds']==nf['preDelay'] and len(f['actions'])==len(nf['actions'])
                for ai,a in enumerate(f['actions']):
                    raw=nf['actions'][ai];assert exact(a['metadata']['native_action'],raw) and a['count']==raw['count'] and a['delay_seconds']==raw['preDelay'] and a['interval_seconds']==raw['interval']
                    if a['kind']=='spawn':
                        born+=a['count'];route=a['spawn']['route'];r=route_ir(native['routes'][raw['routeIndex']],s['map']['rows']);r['motionMode']=meta['native_enemy_bindings'][raw['key']]['motion'] if r['motionMode']=='E_NUM' else r['motionMode']
                        assert all(exact(route[k],v) for k,v in r.items());assert a['spawn']['position']==r['startPosition'];assert a['spawn']['placement']['offset']=={'row':-r['spawnOffset']['y'],'col':r['spawnOffset']['x']} and a['spawn']['placement']['random_range']=={'row':r['spawnRandomRange']['y'],'col':r['spawnRandomRange']['x']}
        assert born==meta['source_births']==(35 if name.endswith('10') else 37)
        controls=[d for d in p['definitions'] if d['kind']=='control' and 'native_story_key' in d.get('metadata',{})];assert len(controls)==1;c=controls[0];acks=[i for i,step in enumerate(c['steps']) if step['kind']=='ack'];assert len(acks)==(3 if name.endswith('10') else 2) and c['ack_policy']=='external' and any(step=={'kind':'delay','seconds':.3} for step in c['steps'])
        # Unique legal cells are chosen deterministically. This is a finite
        # feasibility input, not an optimized or winning stage strategy.
        available={kind:[{'row':i//s['map']['cols'],'col':i%s['map']['cols']} for i,t in enumerate(s['map']['tiles']) if t['buildableType'] in (mask,3)] for kind,mask in [('ground',1),('high',2)]};constraints=[];used=set();commands=[{'at':3+3*i,'action':'control_ack','control':'control/1','step':step} for i,step in enumerate(acks)];spent=0;last=30
        for index,uid in enumerate(s['roster']):
            d=rawdefs[uid];cost=d['components']['attributes']['base']['deploy_cost'];terrain=d['components']['deployable']['terrain'];cells=available[terrain];constraints.append({'unit':uid,'declared_first_deploy_cost':cost,'terrain':terrain,'native_legal_cells':copy.deepcopy(cells),'capacity_limit':8,'can_initially_afford':cost<=10})
            if index>=8:continue
            cell=next(x for x in cells if (x['row'],x['col']) not in used);used.add((cell['row'],cell['col']));at=max(last,math.ceil(max(0,spent+cost-10))*30+31);guaranteed=min(99,10+(at-1)//30-spent);assert guaranteed>=cost
            commands.append({'at':at,'action':'deploy','entity':uid,'alias':'fixed12/'+uid.rsplit('/',1)[1],'row':cell['row'],'col':cell['col'],'facing':'right'});spent+=cost;last=at+450
        command_doc={'schema':'ark-sim/chapter0-public-finite-plan/v1','source_package_sha256':sha(path),'commands':commands,'constraints':constraints,'deployment_count':8,'roster_available':12,'guaranteed_funding':'Native DP10 and 1/sec only; no skill income, refund or injection assumed. At each deployment, use conservative ticks strictly before its logical tick.','limitations':['First eight unique units occupy max8 slots; other four roster units need a future explicit withdraw/redeploy strategy','Legal-cell feasibility is not enemy-route tactical coverage or a whole-stage winning plan','Story ACK dwell is explicit external reference, not native UI measured timing'],'whole_stage':False}
        cmdpath=folder/(name+'.public.plan.v2.json');cmdpath.write_text(json.dumps(command_doc,ensure_ascii=False,indent=2)+'\n',encoding='utf8');Compiler().compile(p)
        records.append({'stage':name,'source_package_sha256':sha(path),'source_births':born,'story_external_ACKs':len(acks),'public_plan_sha256':sha(cmdpath),'typed_author_input_passed':True,'independent_review_pending':True,'whole_stage':False})
    out=ROOT/'validation/campaign/chapter0_stage_assembly_v1/input.review.v2.json';out.write_text(json.dumps({'schema':'ark-sim/chapter0-author-typed-input/v2','records':records,'passed':True,'reviewer_sha256':sha(Path(__file__)),'independent_admission':False,'whole_stage':False},indent=2)+'\n',encoding='utf8');print(json.dumps(records))
if __name__=='__main__':main()
