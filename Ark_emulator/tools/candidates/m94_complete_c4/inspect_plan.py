"""Read exact immutable stage fields for public roster planning."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 p=json.loads((ROOT.parent/'unpack_work/campaign_m91_complete_c4_candidate/stage/level_main_04-09.m92.first_hit.source_circle.prepared.json').read_bytes());s=p['scenarioDraft'];defs={d['id']:d for section in ['entities','abilities','rules','definitions'] for d in p.get(section,[])}
 print(json.dumps({'tiles':[(divmod(i,s['map']['cols']),t['tileKey'],t['buildableType']) for i,t in enumerate(s['map']['tiles']) if t['buildableType']],'parameters':s.get('parameters'),'resources':s['resources'],'objectives':s['objectives'],'roster':s['roster'],'rules':s['rules']},ensure_ascii=False))
 for uid in s['roster']:
  d=defs[uid];print(json.dumps({'id':uid,'attributes':d['components'].get('attributes',{}).get('base'),'deployable':d['components'].get('deployable'),'abilities':d['components'].get('abilities'),'sp':d['components'].get('resources',{}).get('sp')}))
if __name__=='__main__':main()
