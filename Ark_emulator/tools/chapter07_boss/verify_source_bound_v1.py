"""New-identity managed-source bound proof, persistent disk CP and public head."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.runtime).resolve()))
    sys.path.insert(1, str(ROOT))
    from ark_sim import Compiler, Engine
    from ark_sim.adapters.api import implementation_digest
    from ark_sim.contracts import thaw
    from ark_sim.tools.replay import replay
    from tools.chapter07_boss.test_releasewave_v2 import package, deploy, kill, ev
    from tools.chapter07_boss.policies_v2 import providers
    from tools.campaign_ordered_checkpoint import write_ordered, load_bound
    folder = ROOT / 'packages/campaign/chapter07_boss/patrt'
    out = folder / 'source_bound_v1'
    out.mkdir(exist_ok=True)
    guarded = [folder / name for name in ['source.closure.json', 'releasewave.mechanism.v1.json', 'source.consumer.v1.json']]
    before = {str(p):sha(p) for p in guarded}
    expected = '4f16ac4c8ec0c0080302dfa1b6b1b6cc4da90d383ae9a2da5f796551d630c346'
    actual = implementation_digest()
    assert actual == expected, (actual, expected)
    p = package()
    p['manifest'] = json.loads((folder/'source.consumer.v1.json').read_bytes())['manifest']
    s = Engine.create(Compiler(providers=providers()).compile(p), providers=providers(), seed=7187)
    deploy(s); kill(s,35); s.session.advance(36)
    cp = out/'waiting36.checkpoint.json'
    cp_pin = write_ordered(cp,s.checkpoint())
    restored = Engine.restore(s.program,load_bound(cp,cp_pin),providers=providers())
    s.session.advance(25); restored.session.advance(25)
    head = replay(s.program,s.export_replay(),providers=providers())
    assert s.snapshot() == restored.snapshot() == head.snapshot()
    assert s.ctx.resources.current('boss','hp') == 0 and s.ctx.alive('boss') and not s.ctx.active('boss')
    assert s.ctx.attributes.value('boss','atk') == 2240
    assert len(ev(s,'timeline.finish_requested')) == 1
    packets = [e for e in ev(s,'damage.accepted') if e['payload'].get('source') == s.session.world.resolve('boss')]
    assert len(packets)==1 and packets[0]['time']==59 and abs(packets[0]['payload']['amount']-116.704)<1e-9
    for name,data in [('scenario.json',thaw(s.program.scenario)),('replay.json',thaw(s.export_replay())),('observations.json',thaw(s.session.events))]:
        (out/name).write_bytes((json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())
    after = {str(p):sha(p) for p in guarded}
    assert before == after
    result = {'status':'passed','runtime_sha256':actual,'source_guards_before':before,'source_guards_after':after,'new_content_identity_actual':True,'cp_tick':36,'end_tick':61,'cp_equal':True,'head_equal':True,'hp':0,'active':False,'alive':True,'current_atk':2240,'immo_packets':[(e['time'],e['payload']['amount']) for e in packets],'scope':'Short real managed-wave firstdown/ReleaseWave/current-ATK waiting Immo, new content identity; does not replace long future-birth source receipt or ore/mine integration','files':{str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name != 'report.json'}}
    (out/'report.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'status':result['status'],'report':str(out/'report.json'),'sha256':sha(out/'report.json')}))

if __name__ == '__main__':main()
