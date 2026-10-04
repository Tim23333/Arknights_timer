"""Fresh explicit V6 run profile, preserving the original M96+V5 artifacts."""
import hashlib,json
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4';RUNTIME=ROOT.parent/'unpack_work/campaign_m94_complete_c4_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 source=OUT/'runthrough_launch.m96_v6.prepared.json';launch=json.loads(source.read_bytes());old=Path(launch['package']);assert sha(old)==launch['package_sha'];p=json.loads(old.read_bytes());before=deepcopy(p);profile=p['scenarioDraft']['metadata']['runthrough_profile'];profile.update(id='level_main_04-09.m96.public_v6.life99999',public_commands_variant='v6',public_commands_sha256=launch['commands_sha']);check=deepcopy(p)
 for key in ('id','public_commands_variant','public_commands_sha256'):del check['scenarioDraft']['metadata']['runthrough_profile'][key]
 assert check==before
 package=RUNTIME/'stage/level_main_04-09.m96.v6.life99999.runthrough.prepared.json';dest=OUT/'runthrough_launch.m96_v6.named.prepared.json'
 if package.exists() or dest.exists():raise ValueError('Preserve original profile')
 package.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='');launch.update(package=str(package),package_sha=sha(package),profile_id=profile['id'],status='Root-authorized M96+V6 next full V15 run; wait original V3 full replay completion; no concurrent full bounded run');dest.write_text(json.dumps(launch,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'package_sha':sha(package),'commands_sha':launch['commands_sha'],'named_launch_sha':sha(dest)}))
if __name__=='__main__':main()
