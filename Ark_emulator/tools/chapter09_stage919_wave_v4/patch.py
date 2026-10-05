"""Only the stage-bound native next-wave request; frozen consumer unchanged."""
import json,copy,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v3.life99999.json'
OUTPUT=PARENT.with_name('level_main_09-17.native_draft.v4.life99999.json')
SOURCE=PARENT.with_name('level_main_09-17.mandra_next_wave.source.v4.json')
REQUEST={'op':'finish_timeline_wave','target':'source','parameters':{
    'finish_and_skip':False,'track_source_at_next_wave':False,'track_source_wave_delta':0,'track_all_managed_at_next_wave':False}}
def build():
    data=json.loads(PARENT.read_bytes());source=json.loads(SOURCE.read_bytes())
    node=source['templates']['finish_current_wave_when_buff_finish']['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
    assert node['_sourceType']=='BUFF_OWNER' and not node['_finishAndSkip'] and not node['_trackSourceAtNextWave']
    assert node['_trackSourceAtWaveDelta']==0 and not node['_trackAllManagedEnemiesAtNextWave']
    child=copy.deepcopy(data);boss=next(d for d in child['definitions'] if d['id']=='unit/ch9/mandra/body')
    before=copy.deepcopy(boss['components']['rebirth']['on_finish']);assert REQUEST not in before
    boss['components']['rebirth']['on_finish'].append(copy.deepcopy(REQUEST))
    restored=copy.deepcopy(child);next(d for d in restored['definitions'] if d['id']=='unit/ch9/mandra/body')['components']['rebirth']['on_finish'].pop()
    assert restored==data
    return child,before
if __name__=='__main__':
    child,before=build();assert not OUTPUT.exists();OUTPUT.write_text(json.dumps(child,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();receipt={'schema':'ark-sim/source919-wave-hook-patch/v4','parent_sha256':sha(PARENT),'output_sha256':sha(OUTPUT),'source_sha256':sha(SOURCE),'helper_sha256':sha(Path(__file__)),'before':before,'appended':REQUEST,'only_selected_hook_diff':True,'native_input_births':63,'wave_tracking_flags_all_false':True,'source_birth_count_reduced':False,'runtime_changed':False}
    path=ROOT/'validation/campaign/chapter09_stage919_wave_v4/patch.v4.json';assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))
