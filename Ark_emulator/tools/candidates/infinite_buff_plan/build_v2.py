"""Fresh fb599 candidate: actual resolved duration validation in the original atomic plan."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_chapter06_static_selfremove_v1_candidate';OLD=ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v1_candidate';OUT=ROOT.parent/'unpack_work/campaign_infinite_buff_plan_v2_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return subprocess.check_output([sys.executable,'-c','import sys;sys.path.insert(0,sys.argv[1]);from ark_sim.adapters.api import implementation_digest;print(implementation_digest())',str(root)],cwd=root,text=True).strip()
def main():
 assert core(BASE)=='fb599602df2fcdf1e7eb4aacc294084a064b8810461e95437496178cb524ef7b' and core(OLD)=='b20d8bd43e6db219186dca4c01c759b4fa3b44262bddbb5173ab952bf256b188' and not OUT.exists();before={p.relative_to(BASE).as_posix():sha(p) for p in (BASE/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'));file=OUT/'ark_sim/domains/buff_application.py';text=(OLD/'ark_sim/domains/buff_application.py').read_text(encoding='utf8')
 helper="""
def validate_permanent_duration(ctx, source, target, buff_id):
    # Same public attribute calculations and complete scope as BuffSystem.apply.
    # The enclosing Session.atomic rolls back traces/cache epoch/state on reject.
    definition = ctx.program.definitions[buff_id]
    attrs = ctx.attributes.values(source)
    parameters = {**thaw(definition.get('parameters', {})),
                  'duration_seconds': definition.get('duration_seconds', 0),
                  'interval_seconds': definition.get('interval_seconds', 0)}
    duration = ctx.calc('buff.duration', {'attributes': attrs, 'buff_parameters': parameters},
                        source=source, target=target, local=definition.get('rules', {}),
                        rule_id=definition.get('duration_rule'))
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration != 0:
        raise ValueError('Permanent application requires actual resolved zero duration')

"""
 assert text.count('def execute(system,')==1;text=text.replace('def execute(system,',helper+'def execute(system,');old="""        if not plan['accepted'] or not plan['operations']: return False
        mutated = False""";new="""        if not plan['accepted'] or not plan['operations']: return False
        for op in plan['operations']:
            if op['kind'] == 'apply' and op['duration_seconds'] is None:
                validate_permanent_duration(ctx, source, target, op['buff'])
        mutated = False""";assert text.count(old)==1;text=text.replace(old,new)
 old="""                ctx.buffs.apply(source, target, op['buff'], op.get('stacks', 1), duration_override=op['duration_seconds'])
                mutated = True""";new="""                permanent = op['duration_seconds'] is None
                if permanent:
                    # Earlier entries and their callbacks may change actual inputs.
                    validate_permanent_duration(ctx, source, target, op['buff'])
                uid = ctx.buffs.apply(source, target, op['buff'], op.get('stacks', 1), duration_override=op['duration_seconds'])
                if permanent and identity(target) == target_at_entry:
                    current = next((b for b in ctx.get(target, ('buffs', 'instances'), []) if b['id'] == uid and b['definition'] == op['buff']), None)
                    # A legitimate callback may already remove this handle/owner.
                    if current is not None and current['expires_at'] is not None:
                        raise ValueError('Permanent application produced a finite live Buff')
                mutated = True""";assert text.count(old)==1;text=text.replace(old,new);file.write_text(text,encoding='utf8',newline='');after={p.relative_to(OUT).as_posix():sha(p) for p in (OUT/'ark_sim').rglob('*') if p.suffix in ('.py','.json')};assert set(before)==set(after);changed=[p for p in before if before[p]!=after[p]];assert changed==['ark_sim/domains/buff_application.py'];r={'core':core(OUT),'parent_core':core(BASE),'old_b20_core':core(OLD),'candidate':str(OUT),'changed':changed,'parent_guards':before,'candidate_guards':after,'source_primary_modified':False};out=ROOT/'validation/campaign/infinite_buff_plan_v2_actual_duration/composition.json';out.parent.mkdir(parents=True,exist_ok=True);assert not out.exists();out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'core':r['core'],'composition_sha':sha(out)}))
if __name__=='__main__':main()
