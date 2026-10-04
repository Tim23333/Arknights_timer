"""Exact fixed56 story and manifest-bound Opera commands, no runtime approval."""
import json,hashlib,re,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'packages/campaign/chapter08_stage_controls/source';COMMIT='56aee3d6c5a29c3a0d192456d70d14252cbb0804'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def strictfinite(v):
    if isinstance(v,dict):
        for x in v.values():strictfinite(x)
    elif isinstance(v,list):
        for x in v:strictfinite(x)
    elif type(v) is float:assert math.isfinite(v)
def main():
    plan=ROOT/'packages/campaign/chapter08_source_prepare/integration/source.plan.v1.json';native=json.loads(plan.read_bytes())['stages']['level_main_08-17']['native_document'];story=OUT/'main_08-17.fixed56.txt';text=story.read_bytes().decode('utf8');frozen=ROOT/'packages/campaign/chapter08_source_prepare/integration/predefines.native.v2.json';old=json.loads(frozen.read_bytes())['stories']['obt/tutorial/level/main_08-17']
    assert sha(story)==old['payload_sha256']=='f1183cb007820286a097d797035fc22394f4debb843ceaeb12cc48a4bcf0704d'
    assert text==old['script']
    lines=[]
    for number,line in enumerate(text.splitlines(),1):
        m=re.fullmatch(r'\[([A-Za-z]+)\((.*?)\)\]\s*(.*)',line);assert m,line
        lines.append({'line':number,'raw':line,'command':m[1],'parameter_text':m[2],'text':m[3]})
    assert [r['command'] for r in lines]==['HEADER']+['PopupDialog']*8+['Blocker']
    story_actions=[];opera_actions=[]
    for wi,w in enumerate(native['waves']):
        for fi,f in enumerate(w['fragments']):
            for ai,a in enumerate(f['actions']):
                if a['actionType'] not in ('STORY','PLAY_OPERA'):continue
                record={'wave':wi,'fragment':fi,'action':ai,'native':a,'route':native['routes'][a['routeIndex']]}
                (story_actions if a['actionType']=='STORY' else opera_actions).append(record)
    assert len(story_actions)==1 and len(opera_actions)==17
    manifest=OUT/'hot_update_list.fixed56.json';mf=json.loads(manifest.read_bytes());entry=next(v for v in mf['abInfos'] if v['name']=='config/common.ab');ab=OUT/'config_common.fixed56.ab'
    assert ab.stat().st_size==entry['abSize']==40096 and hashlib.md5(ab.read_bytes()).hexdigest()==entry['md5']=='e0e6455db0e79b3499b711cf36e6451c'
    decoded=OUT/'config_common.decoded.json';config=next(v for v in json.loads(decoded.read_bytes())['monos'] if v['raw'].get('m_Name')=='main_08-17');commands={}
    for row in config['raw']['_commands']:
        assert row['key'] in ('blast_effect_x','blast_effect_y') and type(row['duration']) is float and row['duration']==3.0
        assert row['operaNodes']['SerializedObjectReferences']==[]
        nodes=json.loads(row['operaNodes']['SerializedState']);strictfinite(nodes)
        assert [v['$type'] for v in nodes]==['Torappu.Battle.Opera.CameraShake','Torappu.Battle.Opera.ColorGrading','Torappu.Battle.Opera.GlobalAudio']
        assert [v['_preDelay'] for v in nodes]==[.3,0.0,.2]
        commands[row['key']]={'raw':row,'parsed_nodes':nodes,'semantic_class':'camera/screen/audio only, no Buff/Tile/Spawn/Kill/Pause node or serialized object reference','completion_seconds':3.0}
    assert set(commands)=={a['native']['key'] for a in opera_actions}
    dump=ROOT.parent/'Ark_data/Il2CppDumper_current/dump.cs';data=dump.read_text(encoding='utf8');start=data.index('// Namespace: Torappu.Battle.Opera\n[CreateAssetMenu');end=data.index('// Namespace:',data.index('public class Act46SideCreateOrCleanMapEffect',start)+100)
    excerpt=OUT/'opera.schema.dump.excerpt.txt';assert not excerpt.exists();excerpt.write_text(data[start:end],encoding='utf8')
    files=[plan,frozen,story,manifest,ab,OUT/'config_common.fixed56.dat',decoded,OUT/'fixed56.tree.json',OUT/'opera.local_search.v1.json',OUT/'lz4ak.Block.pinned.py',OUT/'lz4ak.instrumentation_removed.py',excerpt,Path(__file__)]
    result={'schema':'ark-sim/chapter08-story-opera-source/v1','fixed_commit':COMMIT,'source_locks':{str(p):sha(p) for p in files},
        'source_urls':{'story':'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/'+COMMIT+'/cn/gamedata/story/obt/tutorial/level/main_08-17.txt','manifest':'https://raw.githubusercontent.com/ArknightsAssets/ArknightsGamedata/'+COMMIT+'/cn/hot_update_list.json','opera_archive':'https://ak.hycdn.cn/assetbundle/official/Android/assets/'+mf['versionId']+'/config_common.dat','decoder':'https://github.com/isHarryh/Ark-Unpacker/blob/4a4b9efc6be4690b68b70b4a16578950baa066d3/src/lz4ak/Block.py'},
        'story':{'key':'obt/tutorial/level/main_08-17','fixed_payload_sha256':sha(story),'local_unpacked_payload_equal':True,'raw_utf8_script':text,'commands':lines,'native_actions':story_actions,'source_header':{'is_skippable':True,'is_autoable':False},'required_popup_ack_count':8,'final_blocker':{'fadetime_seconds':.3,'block':True,'alpha':0,'source_reference_quantized_fade_ticks':9},
            'consumer_policy':'8 source-ordered real popup prompts, preserved actor heads/text, final9tick fade/reference input blocker. Driver may acknowledge each actually requested controlID through public API with durable recorded commands, explicitly deterministic fixture/feedback policy. Header autoable=false forbids claiming native automatic story progression. No fabricated acknowledgement metadata or blank story emit. Native gameplay pause/origin accounting must be explicit reference policy and CP-tested.'},
        'opera':{'key':'main_08-17','manifest_version':mf['versionId'],'manifest_entry':entry,'asset_path':'dyn/config/leveloperaconfig/main_08-17.asset','config_object':config,'commands':commands,'native_actions':opera_actions,
            'classification':'Exact serialized blast_effect_x/y graphs contain only CameraShake/ColorGrading/GlobalAudio. They are audiovisual consumers, not source damage/projectile trajectories. Generic Opera supports gameplay classes, so this classification is specific to these two exact graphs.',
            'consumer_policy':'Explicit source-bound AV request with original route/action identity; schedule ColorGrading at0, GlobalAudio at.2s/6ticks, CameraShake at.3s/9ticks and completion3s/90ticks. Preserve all rawshake/color/audio parameters. Headless runner can record typed audiovisual nodes and completion without HP/SP/Buff/terrain/kill/branch mutation, explicitly visual-state consumer rather than unsupported gameplay no-op.',
            'pending_reference':['Native global OperaController lock/concurrent request arbitration method body unavailable; choose declared request policy, do not assume m_isLocked semantics.','Camera Shake randomness is renderer-only; should not consume battle RNG absent declared renderer state.','Actual audiovisual rendering and source route param placement remain client feedback; no raw node here creates a damage actor.']},
        'extraction_policy':'Original official fixed56 manifest AB MD5/size verified. Standard UnityPy cannot decode custom compression; pinned primary Ark-Unpacker LZ4AK algorithm used in isolated offline extractor, profiling instrumentation only removed. No ark_sim runtime or shared library changed.',
        'version_policy':'Official manifest26-09-22 is pinned by fixed56 and differs from local20260831 asset set. Story exact bytes are identical across those sources. Opera source was missing locally and now supplied from fixed manifest, not silently inferred from names. Current dump schema fields are corroboration only; method bodies unrecovered.',
        'runtime_authored':False,'whole_stage_verified':False,'client_verified':False}
    out=OUT/'story_opera.source.v1.json';assert not out.exists();out.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'path':str(out),'sha256':sha(out),'story_popups':8,'opera_actions':17,'exact_command_count':2}))
if __name__=='__main__':main()
