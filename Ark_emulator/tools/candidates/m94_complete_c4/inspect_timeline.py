"""Read original wave delays before scheduling first deployments."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 p=json.loads((ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate/stage/level_main_04-09.m92.first_hit.source_circle.prepared.json').read_bytes())
 for i,w in enumerate(p['scenarioDraft']['timeline']['waves']):
  print(json.dumps({'wave':i,'header':{k:v for k,v in w.items() if k!='fragments'},'fragments':[{'header':{k:v for k,v in f.items() if k!='actions'},'actions':[{'kind':a['kind'],'count':a.get('count'),'pre':a.get('pre_delay_seconds'),'post':a.get('post_delay_seconds'),'interval':a.get('interval_seconds'),'timing':{k:v for k,v in a.items() if 'delay' in k or 'interval' in k},'native_timing':{k:v for k,v in a.get('metadata',{}).items() if 'native' in k}} for a in f['actions']]} for f in w['fragments']]},ensure_ascii=False))
if __name__=='__main__':main()
