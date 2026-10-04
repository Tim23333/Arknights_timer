"""Opt-in domain settling after each clock step, without executing future tasks."""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m70_buff_applicability_v2_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m84_boundary_settle_v2_candidate'
PIN='0b5a6a6b09cfbb631bd69dd67079814e90bccbe4d5d5737c1d33f869b7fab647'


def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,before,after):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8')
    if s.count(before)!=1:raise ValueError('Source anchor changed '+name)
    p.write_text(s.replace(before,after),encoding='utf8',newline='')


def main(report_path=None):
    if OUT.exists():raise ValueError('Preserve existing candidate')
    assert core(BASE)==PIN
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');source=ROOT.parent/'unpack_work/campaign_m68_deployment_integrated_candidate'/fixture
    if hashlib.sha256(source.read_bytes()).hexdigest()!='f71299c156d27a03d849115df49bd53c1abff79497f233e3266dde1988f6d6fa':raise ValueError('Offline baseline JSON changed')
    (OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,OUT/fixture)
    edit('kernel/session.py','    def _require_idle_registration(self):', '''    def add_boundary_system(self, callback):
        """Settle registered domain state at each new clock boundary.

        This is an explicit opt-in observer, not dispatch of the next frame's
        queued tasks. Registration is part of the checkpoint system signature.
        """
        with self._lock:
            self._require_idle_registration()
            if not callable(callback):raise TypeError('Boundary callback must be callable')
            seq=self.scheduler.reserve_sequence()
            self._systems.append({'callback':callback,'phase':0,'priority':0,'seq':seq,'boundary':True})
            return seq

    def _require_idle_registration(self):''')
    edit('kernel/session.py','                    systems = sorted(self._systems, key=lambda item: (', '                    systems = sorted((s for s in self._systems if not s.get("boundary", False)), key=lambda item: (')
    edit('kernel/session.py','                    self.clock.time += 1', '''                    self.clock.time += 1
                    # Run every step, so segmented and continuous advances
                    # settle the same boundaries and record the same history.
                    for observer in sorted((s for s in self._systems if s.get('boundary',False)),key=lambda s:s['seq']):
                        if callbacks>=self.reaction_budget:raise ReactionBudgetExceeded('Boundary callback exceeds reaction budget')
                        callbacks+=1
                        with self.atomic():observer['callback'](self)''')
    edit('kernel/session.py','"systems": [{key: item[key] for key in ("phase", "priority", "seq")}\n                                  for item in self._systems]', '''"systems": [{**{key: item[key] for key in ("phase", "priority", "seq")},
                                   **({'boundary':True} if item.get('boundary',False) else {})}
                                  for item in self._systems]''')
    edit('kernel/session.py','            for recorded, live in zip(data["systems"], self._systems):\n                integer(recorded["priority"], "system priority")', '''            for recorded, live in zip(data["systems"], self._systems):
                boundary=recorded.get('boundary',False)
                if type(boundary) is not bool or boundary!=live.get('boundary',False):
                    raise ValueError('Restore requires identical boundary system registration')
                integer(recorded["priority"], "system priority")''')
    edit('adapters/api.py','            self.session.add_system(self.ctx.buffs.tick, phase=0)', '''            self.session.add_system(self.ctx.buffs.tick, phase=0)
            if self.ctx.buffs.applicability.enabled:
                self.session.add_boundary_system(self.ctx.buffs.tick)''')
    report={'parent_core':PIN,'core':core(OUT),'actual_root':str(OUT),'status':'constructed, independent oldfail peer and other tests pending'}
    target=report_path or ROOT/'validation/campaign/m84_boundary_settle/composition.json'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-root',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    if args.output_root is not None:OUT=args.output_root.resolve()
    main(args.report)
