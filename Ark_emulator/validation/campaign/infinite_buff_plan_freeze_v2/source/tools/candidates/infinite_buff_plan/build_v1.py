"""Single-file explicit permanent application over fixed fb599 joint candidate."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';OUT=ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate';PARENT='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)==PARENT and not OUT.exists();before={str(p.relative_to(BASE)):sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/buff_application.py';text=file.read_text(encoding='utf8');text=text.replace('def validate_plan(plan, allowed, target, instances):','def validate_plan(plan, allowed, target, instances, definitions=None):')
 old="""            n = op.get('duration_seconds')
            if type(n) not in (int, float) or not math.isfinite(n) or n < 0: raise ValueError('Finite nonnegative application duration required')"""
 new="""            if 'duration_seconds' not in op:
                raise ValueError('Explicit application duration required')
            n = op['duration_seconds']
            if n is None:
                definition = (definitions or {}).get(op['buff'])
                # None opts into the existing declared permanent Buff lifetime.
                # Validate every item before execution; no partial application.
                if not isinstance(definition, Mapping) or definition.get('kind') != 'buff' or 'duration_seconds' in definition or 'duration_rule' in definition:
                    raise ValueError('Permanent application requires a declared permanent Buff')
                parameter_duration = definition.get('parameters', {}).get('duration_seconds', 0)
                if type(parameter_duration) not in (int, float) or not math.isfinite(parameter_duration) or parameter_duration != 0:
                    raise ValueError('Permanent Buff parameters cannot declare a finite lifetime')
            elif type(n) not in (int, float) or not math.isfinite(n) or n < 0:
                raise ValueError('Finite nonnegative application duration required')"""
 assert text.count(old)==1;text=text.replace(old,new);oldcall='validate_plan(plan, allowed, target, instances)';assert text.count(oldcall)==1;text=text.replace(oldcall,'validate_plan(plan, allowed, target, instances, ctx.program.definitions)');file.write_text(text,encoding='utf8',newline='');after={str(p.relative_to(OUT)):sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};changed=[p for p in before if before[p]!=after[p]];assert changed==['ark_sim/domains/buff_application.py'];assert before=={str(p.relative_to(BASE)):sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};r={'core':core(OUT),'parent_core':PARENT,'candidate':str(OUT),'changed':changed,'parent_guards':before,'candidate_guards':after,'source_primary_modified':False};out=ROOT/'validation/campaign/infinite_buff_plan_v1/composition.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'composition_sha':sha(out),'one_file':changed}))
if __name__=='__main__':main()
