import sys,json,hashlib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PARENT=ROOT.parent/'unpack_work/campaign_projectile_leaf_v1_candidate';OUT=ROOT.parent/'unpack_work/campaign_world_fork_v1_candidate';REPORT=ROOT/'validation/campaign/chapter08_world_fork_v1';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not OUT.exists();REPORT.mkdir(exist_ok=False);shutil.copytree(PARENT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
paths=['kernel/world.py','kernel/transaction.py','kernel/session.py'];before={name:sha(PARENT/'ark_sim'/name) for name in paths}
world=OUT/'ark_sim/kernel/world.py';text=world.read_text(encoding='utf8');text=text.replace('from threading import RLock','from threading import RLock\nfrom copy import deepcopy')
anchor='    def snapshot(self):\n';assert text.count(anchor)==1
methods='''    def _fork_validated(self):
        """Private detached stores; public JSON boundaries remain unchanged."""
        with self._lock:
            fork = World()
            # create(name) permits str subclasses; JSON formerly normalized
            # these metadata values. Never invoke their deepcopy overrides.
            entities = {}
            for key, value in self._entities.items():
                record = dict(value)
                record["definition_id"] = str.__str__(record["definition_id"])
                record["tags"] = [str.__str__(tag) for tag in record["tags"]]
                entities[key] = record
            fork._entities = deepcopy(entities)
            fork._aliases = {str.__str__(key): value for key, value in self._aliases.items()}
            fork._next_id = self._next_id
            fork._versions = dict(self._versions)
            fork._validated_fork = True
            return fork

    def _adopt_validated(self, fork, *, preserve_views):
        """Transfer isolated fork ownership once, with no user-code callback."""
        if type(fork) is not World or fork is self or not getattr(fork, "_validated_fork", False):
            raise ValueError("Expected an unconsumed private validated World fork")
        with self._lock, fork._lock:
            views = {key: cached for key, cached in self._views.items()
                     if key in fork._entities and cached[0] == fork._versions[key]} if preserve_views else {}
            self._entities, self._aliases, self._next_id = fork._entities, fork._aliases, fork._next_id
            self._versions, self._views = fork._versions, views
            # A retained staged object can never mutate the newly published data.
            fork._entities, fork._aliases, fork._versions, fork._views = {}, {}, {}, {}
            fork._next_id, fork._validated_fork = 1, False

'''
text=text.replace(anchor,methods+anchor);world.write_text(text,encoding='utf8',newline='')
transaction=OUT/'ark_sim/kernel/transaction.py';text=transaction.read_text(encoding='utf8');text=text.replace('    world = World()\n    world.restore(session.world.snapshot())','    world = session.world._fork_validated()')
start=text.index('    session.world._entities = world._entities');end=text.index('    session.scheduler._tasks = scheduler._tasks',start);text=text[:start]+'    session.world._adopt_validated(world, preserve_views=True)\n'+text[end:];transaction.write_text(text,encoding='utf8',newline='')
session=OUT/'ark_sim/kernel/session.py';text=session.read_text(encoding='utf8');assert '"world": self.world.snapshot()' in text and 'self.world.restore(saved["world"])' in text;text=text.replace('"world": self.world.snapshot()','"world": self.world._fork_validated()').replace('self.world.restore(saved["world"])','self.world._adopt_validated(saved["world"], preserve_views=False)');session.write_text(text,encoding='utf8',newline='')
sys.path.insert(0,str(OUT));from ark_sim.adapters.api import implementation_digest
r={'parent_core':'71d33fa18662ae4f19c326988448e4dbb2764e503eec7bf3058e63c6a1182be2','core':implementation_digest(),'delta':{name:{'before':before[name],'after':sha(OUT/'ark_sim'/name)} for name in paths},'scope':'Author isolated implementation only; no promotion/full/base until interface review.'};(REPORT/'composition.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))
