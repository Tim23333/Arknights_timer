"""Correct two independent packet/capacity counters without editing frozen v2."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OLD=ROOT.parent/'unpack_work/campaign_elemental_v2_candidate'
OUT=ROOT.parent/'unpack_work/campaign_elemental_v3_candidate'
OLD_CORE='4ef70d6fb24ecf9819b12d97bc1893005e274278b9a1798ba265ed833bfa0add'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','from ark_sim.adapters.api import implementation_digest;print(implementation_digest())'],cwd=root,text=True).strip()
def main():
    assert core(OLD)==OLD_CORE and not OUT.exists()
    shutil.copytree(OLD/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(HERE/'elemental_v3.py',OUT/'ark_sim/domains/elemental.py')
    effects=OUT/'ark_sim/domains/effects.py';text=effects.read_text(encoding='utf-8')
    before='''            if operation == 'elemental_damage':
                if source is not None and not self.ctx.active(source):continue
                self.ctx.elemental.apply(source,target,effect,cause)
            elif operation == 'elemental_attack':
                if source is not None and not self.ctx.active(source):continue
                # Complete request validated before the health packet. Nested
                # failure rolls health/events/RNG/scheduler back atomically.
                self.execute(source,[target],thaw(effect['health_effect']),ability,cast,cause)
                if self.ctx.active(target) and self.ctx.active(source):
                    self.ctx.elemental.apply(source,target,thaw(effect['element_effect']),cause)'''
    after='''            if operation == 'elemental_damage':
                self.ctx.elemental.apply(source,target,effect,cause,cast=cast)
            elif operation == 'elemental_attack':
                retained=(self.ctx.projectiles is not None and
                          self.ctx.projectiles.retained_payload_allowed(source,target,cast) is True)
                if source is not None and not self.ctx.active(source) and not retained:continue
                packet=thaw(effect)
                projectile=packet['health_effect'].pop('projectile_definition',None)
                if projectile is not None:packet['projectile_definition']=projectile
                # A health projectile carries this whole compound packet. Its
                # actual impact delivers health then EP, never EP at launch.
                if self._projectile(source,target,packet,ability,cast,cause):continue
                self.execute(source,[target],packet['health_effect'],ability,cast,cause)
                if self.ctx.active(target):
                    self.ctx.elemental.apply(source,target,packet['element_effect'],cause,cast=cast)'''
    assert text.count(before)==1;text=text.replace(before,after);effects.write_text(text,encoding='utf-8',newline='')
    oldtest=HERE/'test_author_v2.py';test=HERE/'test_author_v3.py';assert not test.exists()
    test.write_text(oldtest.read_text(encoding='utf-8').replace('campaign_elemental_v2_candidate','campaign_elemental_v3_candidate').replace('chapter09_elemental_author_v2','chapter09_elemental_author_v3'),encoding='utf-8')
    report=ROOT/'validation/campaign/chapter09_elemental_v3';report.mkdir(parents=True,exist_ok=True)
    path=report/'composition.json';assert not path.exists();path.write_text(json.dumps({'parent_candidate_core':OLD_CORE,'candidate':str(OUT),
        'core':core(OUT),'relative_parent_delta':['ark_sim/domains/elemental.py','ark_sim/domains/effects.py'],
        'required_old_actual_failures':{'fresh_root_helper':str(ROOT/'tools/chapter09_elemental_review/test_root_peer_v2.py'),
             'sha256':sha(ROOT/'tools/chapter09_elemental_review/test_root_peer_v2.py'),'on_v2_actual':{'tests':2,'failed':2,'EP_early':18,'EP_expected_unhit':19,'clamped_loss_actual':18,'expected':6}},
        'old_frozen_modified':False},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'core':core(OUT),'composition_sha':sha(path)}))

if __name__=='__main__':main()
