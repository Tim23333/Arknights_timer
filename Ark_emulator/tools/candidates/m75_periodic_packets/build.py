"""Independent M75 packet-chain successor; frozen M73 remains untouched."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m73_environment_integrated_v2_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m75_periodic_packets_candidate'
PIN='1b548c29fba3dd19c177fbb458a0226e496b15a03c5c2a3599243bcb20e40932'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def edit(name,before,after):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8')
    if s.count(before)!=1:raise ValueError('Changed packet source anchor '+name+':'+before)
    p.write_text(s.replace(before,after),encoding='utf8',newline='')

def main():
    assert core(BASE)==PIN
    if OUT.exists():raise ValueError('Candidate exists; no overwrite')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    fixture=Path('ark_emulator/levels/packs/level_main_00-01.json');(OUT/fixture).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/fixture,OUT/fixture)
    p=OUT/'ark_sim/domains/periodic_fields.py';s=p.read_text(encoding='utf8')
    start=s.index('    def pulse(self,session,payload):');s=s[:start]+Path(__file__).with_name('packet_methods.py').read_text(encoding='utf8')
    start=s.index('    def remove(self,uid):');end=s.index('    def tick(self,session):',start)
    s=s[:start]+Path(__file__).with_name('remove_method.py').read_text(encoding='utf8')+s[end:]
    p.write_text(s,encoding='utf8',newline='')
    edit('domains/periodic_fields.py',"'sequence':0,'generation':1,'active':True,'due':None,'task':None", "'sequence':0,'generation':1,'active':True,'due':None,'task':None,'task_seq':None,'packet_chain':None")
    edit('domains/periodic_fields.py',"due=self.ctx.session.time+ticks;task=self.ctx.session.schedule('domain.field.pulse',{'uid':uid,'generation':field['generation']},due,phase=0)","due=self.ctx.session.time+ticks;task_seq=self.ctx.session.scheduler._next_seq;task=self.ctx.session.schedule('domain.field.pulse',{'uid':uid,'generation':field['generation'],'sequence':field['sequence']},due,phase=0)")
    edit('domains/periodic_fields.py','data=self.state();data[\'fields\'][uid].update(due=due,task=task);self.save(data)',"data=self.state();data['fields'][uid].update(due=due,task=task,task_seq=task_seq);self.save(data)")
    edit('domains/periodic_fields.py', "        ticks=self.ctx.quantize(seconds)",
        "        if field.get('packet_chain') is not None or field.get('task') is not None:\n            raise ValueError('Field already owns a packet chain or pending pulse')\n        ticks=self.ctx.quantize(seconds)")
    edit('domains/context.py','        self.effect_phase = len(program.ruleset.get("system_order", ())) + 1','        self._base_effect_phase = len(program.ruleset.get("system_order", ())) + 1')
    edit('domains/context.py','    def entity(self, ref):', '''    @property
    def effect_phase(self):
        # Numeric packet stages are opt-in. Ordinary no-profile execution retains
        # exactly its original phase; no source=None relaxation is added here.
        base = self._base_effect_phase
        if self.periodic_fields is not None and self.session._active_key is not None:
            return max(base, self.session._active_key[1])
        return base

    @effect_phase.setter
    def effect_phase(self, value):
        self._base_effect_phase = value

    def entity(self, ref):''')
    edit('domains/context.py','    def react(self, session, payload):\n        self.resources.notify', '''    def react(self, session, payload):
        if self.periodic_fields is not None:
            with session.atomic():
                return self._react(session, payload)
        return self._react(session, payload)

    def _react(self, session, payload):
        self.resources.notify''')
    edit('adapters/api.py',"            self.session.register_handler('domain.field.pulse',self.ctx.periodic_fields.pulse)","            self.session.register_handler('domain.field.pulse',self.ctx.periodic_fields.pulse)\n            self.session.register_handler('domain.field.packet',self.ctx.periodic_fields.packet)")
    report={'parent_core':PIN,'core':core(OUT),'sources':{str(p.relative_to(OUT)):sha(p) for p in sorted((OUT/'ark_sim').rglob('*.py'))}}
    target=ROOT/'validation/campaign/m75_packets/composition.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'core':report['core']}))

if __name__=='__main__':main()
