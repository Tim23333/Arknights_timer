"""Read source components and stage instances, no runtime dummy authoring."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 path=ROOT/'packages/campaign/chapter05_predefines/source.reference.json';p=json.loads(path.read_bytes());print(json.dumps({'sha':hashlib.sha256(path.read_bytes()).hexdigest(),'keys':list(p),'skill':p['selected_skill_level']}))
 for key,value in p.items():
  if isinstance(value,dict) and 'components' in value:
   print(json.dumps({'section':key,'classes':[(k,c.get('native_class')) for k,c in value['components'].items()]}))
   for k,c in value['components'].items():
    if c.get('native_class') in ('TrapMode','FarthestPointMovement','HitBehaviour','SimpleProjectile'):print(json.dumps({'section':key,'component':k,'class':c['native_class'],'raw':c['raw']}))
 print(json.dumps({'stages':p.get('stages'), 'otherStageKeys':{k:v for k,v in p.items() if 'stage' in k}},ensure_ascii=False)[:10000])
if __name__=='__main__':main()
