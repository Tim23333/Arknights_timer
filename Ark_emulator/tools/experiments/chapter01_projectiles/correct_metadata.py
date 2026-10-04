import json,hashlib,argparse
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'packages/campaign/chapter01_models/projectile_lifecycle';OUT=BASE/'metadata_corrected'
PINS={'model.json':'8d416e8c72e1b3524f5bd6201b6216b42a5d14d9bba4129433c73b9ed58f2c44','follow.model.json':'8ec2438806ab294d659e702cc46ba7da10630f27eedbb067b63bc51897e0a25a','first_signal.model.json':'d4238bfdbe3233563b9b4558b80193519cd3c3a97b0f16b64f0847eaf08a865e'}
def build(name):
 raw=(BASE/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==PINS[name];old=json.loads(raw);new=deepcopy(old);meta=new['manifest']['metadata'];profile=meta['profiles'];mode=next(p for p in new['projectiles'] if p['id']=='projectile/chapter01_w/c4')['motion']['parameters']['mode']
 profile['C4_bomb']=f'actual logical attachment instance: authored windup.6/lifetime3.2; {mode} position policy; expiry area at stored projectile point; pending cast completes on actual invalidation; overlapping packets settle separately'
 profile['sampling']='both normal/C4 damage source ATK at_hit, target DEF at settlement; source/target invalid policies belong to explicit projectile lifecycle; source cast interrupt and detached object retention are distinct'
 profile['normal_packet']['flight']='world projectile instance: pure planar homing speed5/visual parabola/swept trace-point model; life10/reach/end-hit/max1 quota; captured identity and explicit invalid/hidden policies'
 profile['normal_packet']['C4_interlock']='cancel unlaunched normal tasks at C4 start; retain launched objects; block normal until pending projectile invalidations actually close cast'
 meta['model_gaps']=['Full native Boss FSM/collision/mount/control reconstruction is outside this declared-profile module']
 meta['client_pending']+=['Native Paracurve/body/collision and lifecycle callback bodies unrecovered despite executable mathematical adapter','Native AttachToTarget parent transform may follow independently of follow flag; fixed/follow profiles do not prove native semantics','Native area radius/source sampling/callback ordering remain unverified method body calibration']
 meta['metadata_revision']={'old_package_sha256':PINS[name],'reason':'Independent peer actual live+100ATK at114 yielded926; inherited at_cast/fixed-delay/not-converted prose was stale','executable_sections_unchanged':True,'formal_approval':False}
 assert all(new[k]==old[k] for k in old if k!='manifest')
 a=deepcopy(new['manifest']);b=deepcopy(old['manifest']);a.pop('metadata');b.pop('metadata');assert a==b
 return new
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 for name in PINS:
  raw=(json.dumps(build(name),ensure_ascii=False,indent=2)+'\n').encode('utf8');path=OUT/name
  if args.check:assert path.read_bytes()==raw
  else:path.write_bytes(raw)
  print(name,hashlib.sha256(raw).hexdigest())
