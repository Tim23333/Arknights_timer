"""Literal source phase0 Buff ON_FINISH, not a synthetic on_begin release."""
from pathlib import Path
import json
from tools.chapter07_boss.build_mechanism_v1 import OUT,UID,sha
RELEASE='buff/'+UID+'/release_wave'
def main():
 old=OUT/'combined.mechanism.v2.json';p=json.loads(old.read_bytes());s=json.loads((OUT/'source.closure.json').read_bytes());node=s['bson_templates']['finish_current_wave_when_buff_finish']['parsed']['eventToActions']['ON_BUFF_FINISH'][0]
 assert node['_sourceType']=='BUFF_OWNER' and node['_finishAndSkip'] is False and node['_trackSourceAtNextWave'] is False and type(node['_trackSourceAtWaveDelta']) is int and node['_trackSourceAtWaveDelta']==0 and node['_trackAllManagedEnemiesAtNextWave'] is False
 p['buffs'].append({'id':RELEASE,'kind':'buff','on_remove':[{'op':'finish_timeline_wave','target':'source','parameters':{'finish_and_skip':node['_finishAndSkip'],'track_source_at_next_wave':node['_trackSourceAtNextWave'],'track_source_wave_delta':node['_trackSourceAtWaveDelta'],'track_all_managed_at_next_wave':node['_trackAllManagedEnemiesAtNextWave']}}],'metadata':{'native_buff':'patrt_t_state_1[release_wave]','native_on_finish_document_sha256':s['bson_templates']['finish_current_wave_when_buff_finish']['document_sha256'],'source_phase0_parent':'Modes/Default/Talents/ReleaseWave'}})
 p['entities'][0]['components']['buffs']['initial'].append(RELEASE);p['manifest']['id']='package/ch7/patrt/combined_release_wave_source_v1';meta=p['manifest']['metadata'];meta['builder_sha256']=sha(Path(__file__));meta['source_locks'][str(old)]=sha(old);meta['source_release_callback']='Realphase0 ownedBuff removal byfirsttrueHP0/Rebornclear invokesliteralON_FINISH op; no on_begin replacement/no syntheticdeath. Realmanagedtimeline origin required.';meta['unconsumed_required_mechanisms']=['FullRootore/mine sourcecompatibility/stage/controljoin pending'];path=OUT/'releasewave.mechanism.v1.json';path.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'sha256':sha(path),'stage_export_allowed':False}))
if __name__=='__main__':main()
