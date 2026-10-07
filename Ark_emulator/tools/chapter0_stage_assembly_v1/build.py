"""Complete native chapter0 stages with explicit per-node external story ACK."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter06_review.stage_converter_v7 import compose,exact
from tools.campaign_content_composition_v2 import compose_modules,reachable_content
from ark_sim import Compiler
from ark_sim.adapters.api import implementation_digest
P=ROOT/'packages/campaign/chapter0_source_prepare';M=ROOT/'packages/campaign/chapter0_consumers/enemies.module.v2.json';ROSTER=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';PLACEMENT=ROOT/'packages/campaign/chapter01_stage_models/m26/level_main_01-12.partial.json';OUT=ROOT/'packages/campaign/chapter0_stage_models'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def story_control(key,story):
    steps=[]
    for node in story['commands']:
        command=node['command'];assert command in ('HEADER','PopupDialog','Blocker')
        steps.append({'kind':'effects','effects':[{'op':'emit','target':'battle','event':'reference.story.node','payload':{'native_story_key':key,'native_node':copy.deepcopy(node),'external_reference_only':True}}]})
        if command=='PopupDialog':steps.append({'kind':'ack','key':key+'/line/'+str(node['line'])})
        elif command=='Blocker':
            assert node['parameters']=='fadetime=0.3, block=true, a=0';steps.append({'kind':'delay','seconds':.3})
    return {'id':'control/ch0/story/'+key.replace('/','_'),'kind':'control','clock_policy':'logical','ack_policy':'external',
      'on_start':[{'op':'input_lock','target':'battle','parameters':{'key':'story','enabled':True}}],
      'steps':steps,'metadata':{'native_story_key':key,'native_story_source':copy.deepcopy(story['source']),'native_script':story['script'],'native_commands':copy.deepcopy(story['commands']),
      'reference_policy':'PopupDialog each requires explicit public external ACK; Blocker fade consumes .3 logical seconds; input locked for owned control then automatically released. Combat logical clock continues; UI pause/render/click dwell not recovered.'}}
def build():
    assert sha(P/'source.plan.v3.json')=='b0fde50c99f7f6ddcbc55079b46d822178a5da71f52ab5bc9cc488b54e66c95a';assert sha(M)=='15f7c0e7ec22e7cd39d861895e8bcc0986f6912000db4bff3b25c56817bdbf3f'
    assert implementation_digest()=='08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'
    plan=json.loads((P/'source.plan.v3.json').read_bytes());source=json.loads((P/'enemies.native.v1.json').read_bytes());env=json.loads((P/'environment.native.v1.json').read_bytes());stories=json.loads((P/'stories.native.v1.json').read_bytes())['stories'];enemy=json.loads(M.read_bytes());roster=json.loads(ROSTER.read_bytes());placement=json.loads(PLACEMENT.read_bytes())
    for group in (plan['source_locks'],source['source_locks'],env['source_locks']):
        for path,h in group.items():assert sha(Path(path) if Path(path).is_absolute() else ROOT.parent/path)==h
    assert len(roster['manifest']['metadata']['roster'])==12
    modules=[('native_ch0_v2',enemy),('fixed12_m26',roster),('native_spawn_rectangle',{'rules':[r for r in placement['rules'] if r['id']=='rule/m7_spawn_rectangle']})]
    locks={str(x):sha(x) for x in [P/'source.plan.v3.json',P/'enemies.native.v1.json',P/'environment.native.v1.json',P/'stories.native.v1.json',M,ROSTER,PLACEMENT,Path(__file__),ROOT/'tools/chapter06_review/stage_converter_v7.py']};records=[]
    for stage,row in plan['stages'].items():
        native=copy.deepcopy(row['native_document']);assert not native.get('branches') and not any(native['predefines'].values()) and not native.get('hardPredefines');bindings={}
        for vid in row['variant_ids']:
            ref=plan['variants'][vid]['native_reference'];v=source['variants'][vid];bindings[ref['id']]={'unit':'unit/ch0/'+v['prefab_key'],'motion':'FLY' if v['native_enemy']['resolved']['motion']=='FLY' else 'WALK'}
        storykeys={a['key'] for w in native['waves'] for f in w['fragments'] for a in f['actions'] if a['actionType']=='STORY'};controls={k:story_control(k,stories[k]) for k in storykeys}
        scene,defs=compose(native,stage,bindings,{},story_controls=controls)
        for controller in defs:controller.setdefault('metadata',{})['clock_reference_policy']='Replaceable logical-clock continue policy; native UI/combat pause and external ACK dwell method bodies not recovered. Popup ACK is actual external control; declared Blocker fade .3 logical seconds.'
        scene['roster']=copy.deepcopy(roster['manifest']['metadata']['roster']);scene['rules']=copy.deepcopy(roster['manifest']['metadata']['stage_rules']);scene['resources']['life']={'initial':99999,'capacity':99999}
        assert scene['resources']['dp']['initial']==10 and scene['parameters']['deploy_capacity']==8 and native['options']['moveMultiplier']==.5
        package,composition=reachable_content(scene,[*modules,('native_UI_controls',{'definitions':defs})],manifest_id='package/ch0/native_assembled/'+stage)
        births=sum(a['count'] for w in scene['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn');assert births==row['features']['spawn_count'] and births==(35 if stage.endswith('10') else 37)
        package['manifest']['metadata'].update({'source_locks':locks,'required_runtime':implementation_digest(),'native_document':native,'native_enemy_bindings':bindings,'native_action_records':copy.deepcopy(row['actions']),'source_births':births,'only_base_life_override':99999,'fixed_roster':copy.deepcopy(scene['roster']),
          'UI_reference_policy':'Each native PopupDialog has external ACK; source Blocker .3 is explicit logical delay. Original raw commands remain in control metadata. Native UI pause/render and external ACK dwell are unverified.',
          'whole_stage':False,'client_verified':False,'third_party_review_pending':True,'pending':['Independent full typed source/input review','Public fixed12 finite terrain/cost plan and full execution','Native UI pause/ACK timing bodies and version alignment']})
        program=Compiler().compile(package);OUT.mkdir(parents=True,exist_ok=True);dest=OUT/(stage+'.source.v2.json');assert not dest.exists();dest.write_text(json.dumps(package,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        records.append({'stage':stage,'path':str(dest),'sha256':sha(dest),'source_births':births,'compiled_fingerprint':program.fingerprint,'source_complete':True,'third_party_review_pending':True,'whole_stage':False})
    out=ROOT/'validation/campaign/chapter0_stage_assembly_v1/build.v2.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'schema':'ark-sim/chapter0-stage-assembly/v2','records':records,'source_locks':locks,'core':implementation_digest(),'compiled':True,'whole_stage':False},indent=2)+'\n',encoding='utf8');print(json.dumps(records))
if __name__=='__main__':build()
