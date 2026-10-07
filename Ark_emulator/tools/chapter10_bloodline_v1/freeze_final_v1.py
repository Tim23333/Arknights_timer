"""Export source consumers and pin completed actual evidence; no simulation."""
import json, hashlib, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CAND=(ROOT/'../unpack_work/campaign_c10_bloodline_v1_candidate').resolve()
sys.path.insert(0,str(CAND));sys.path.insert(1,str(ROOT))
from ark_sim.adapters.api import implementation_digest
from tools.chapter10_bloodline_v1.build import build, KEYS, SOURCE, BSON
OUT=ROOT/'validation/campaign/chapter10_bloodline_v1'
MOD=ROOT/'packages/campaign/chapter10_consumers/bloodline'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    assert not p.exists(), str(p)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def pin(p):return {'path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size}
paused=json.loads((OUT/'paused.snapshot.v1.json').read_bytes())
inventory={k:sha(CAND/k) for k in paused['source_inventory']}
assert inventory==paused['source_inventory']
core=implementation_digest();assert core==paused['core']
author=json.loads((OUT/'author.final.resume.v8.json').read_bytes())
domain=json.loads((OUT/'domain46.resume.v2.json').read_bytes())
assert author['actual_exit']==domain['actual_exit']==0
assert len(author['results'])==7 and all(x['passed'] for x in author['results'])
assert author['core_before']==author['core_after']==domain['core_before']==domain['core_after']==core
modules=[]
for key in KEYS:
    path=MOD/(key+'.module.v1.json');write(path,build(key));modules.append(pin(path))
parent=json.loads((OUT/'parent.snapshot.v1.json').read_bytes())
delta=[]
for key,value in inventory.items():
    if parent['source_pins'].get(key)!=value:
        dst=ROOT/'tools/chapter10_bloodline_v1/source_delta.final.v1'/key
        dst.parent.mkdir(parents=True,exist_ok=True);assert not dst.exists()
        shutil.copyfile(CAND/key,dst)
        delta.append({'file':key,'parent_sha256':parent['source_pins'].get(key),'candidate_sha256':value,'copy':pin(dst)})
assert len(delta)==9
receipts=[]
for name in ['chapter10_bloodline_latefault_resume_v1','chapter10_bloodline_latefault_resume_v2','chapter10_bloodline_latefault_resume_v3','chapter10_bloodline_author_resume_v8','chapter10_bloodline_domain46_resume_v2']:
    path=Path('E:/ArkSimLogs/receipts')/name/'completion.json'
    if not path.exists():continue
    receipt=json.loads(path.read_bytes())
    assert receipt['cleanup_exit']==0 and receipt['raw_logs_removed_after_validation']
    receipts.append({**pin(path),'worker_exit':receipt['worker_exit'],'cleanup':receipt['cleanup_result']})
assert len(receipts)==5
reports=[pin(OUT/n) for n in ['author.final.resume.v8.json','domain46.resume.v2.json','latefault.resume.diff.v2.json','latefault.resume.diff.v3.json']]
helpers=[pin(p) for p in sorted((ROOT/'tools/chapter10_bloodline_v1').glob('*.py'))]
write(OUT/'final.freeze.v1.json',{
    'schema':'ark-sim/source-candidate-freeze/v1','status':'author_gates_passed_independent_and_full_pending',
    'candidate':str(CAND),'core':core,'parent_core':parent['core'],'source_inventory':inventory,
    'source_delta':delta,'modules':modules,'helpers':helpers,'source_inputs':[pin(SOURCE),pin(BSON)],
    'actual_reports':reports,'author_groups':7,'original_domain_tests':46,'cleanup_receipts':receipts,
    'deleted_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts),'remaining_raw_files':0,'cleanup_errors':0,
    'interface':{'builder':'tools.chapter10_bloodline_v1.build.build_all() / build(key)','providers':'tools.chapter10_bloodline_v1.build.providers()',
       'mark':'buff/ch10/bloodline/bloodsucker_mark','death_adapter':'attach_death_source(entity, rawResolvedBB, *, death_buff=DEATH, child_resolver=entity_id)',
       'child_keys':'dzoms[_2] for dpvt[_2]; dzomg[_2] can be referenced by dklord[_2]; giant bloodsuckers have no native death-rattle themselves'},
    'event_protocol':{'issued':'source/stamp/death_event/snapshot/spec/spec_digest/membership/rows','born':'source/source_stamp/child/definition/issued_event/death_event/slot/managed_membership/route_inherited/position',
      'pending':'battle.state.death_spawns and timeline.descendant_pending; real parent retires immediately, pending owned births retain timeline obligations'},
    'late_fault_boundary':'actual domain.death_spawn current_task handler atomic entry; full World/scheduler/events/RNG/cache equal; clock and exact framework failure transition verified separately',
    'reference_policies':['Native method bodies unavailable: BB delay/key resolution selected explicitly; raw BSON delay0/key null retained alongside fixed56 BB delay1/key.',
      'randomOffset float32 .10000000149011612 uses named-axis uniform reference provider; spatial obstacle/passability client agreement unverified.',
      'Attack animation max scale and full-duration/attack-cycle interaction explicitly reference policy; no client timing parity claim.'],
    'preserved_failures':[pin(p) for p in sorted(OUT.glob('*.json')) if p.name.startswith(('author.initial','author.fresh','author.strict','fixture.failure','restore.binding'))],
    'paused_snapshot':pin(OUT/'paused.snapshot.v1.json'),'primary_modified':False,'promoted':False,'long_suite_started':False})
print(json.dumps({'freeze':pin(OUT/'final.freeze.v1.json'),'core':core,'delta_files':len(delta),'modules':len(modules),'deleted_bytes':sum(r['cleanup']['reclaimed_bytes'] for r in receipts)},indent=2))
