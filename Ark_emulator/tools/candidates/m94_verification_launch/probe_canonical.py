"""Observe unchanged canonical fixture timing under a selected frozen source."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime-root',type=Path,required=True);args=ap.parse_args();sys.path.insert(0,str(args.runtime_root.resolve()));sys.path.insert(1,str(ROOT))
 import ark_sim
 from ark_sim.adapters.api import implementation_digest
 from ark_sim.contracts import thaw
 assert Path(ark_sim.__file__).resolve().parent==args.runtime_root.resolve()/'ark_sim'
 from tools.witness_canonical_kalts import healing_fixture,mon
 s=healing_fixture(own=False);s.advance(28);host=s.session.world.resolve('host');target=mon(s,'other');events=[thaw(e) for e in s.session.events if e['type'] in ('healing.accepted','healing.rejected','ability.started','ability.interrupted','ability.finished') and e['payload'].get('source')==host]
 print(json.dumps({'core':implementation_digest(),'events':events,'target_hp':s.ctx.resources.current(target,'hp'),'runtime':thaw(s.ctx.get(host,('runtime',)))}))
if __name__=='__main__':main()
