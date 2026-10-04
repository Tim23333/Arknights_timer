"""Build independent M71 from frozen M68; never edit the parent."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT.parent / 'unpack_work/campaign_m68_deployment_integrated_candidate'
OUT = ROOT.parent / 'unpack_work/campaign_m71_event_storage_candidate'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def core(root):
    return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')): sha(p)
        for p in sorted((root/'ark_sim').rglob('*.py'))}, sort_keys=True,
        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def replace(path, before, after):
    source = path.read_text(encoding='utf8')
    if source.count(before) != 1:
        raise ValueError(f'Changed patch anchor: {path}: {before}')
    path.write_text(source.replace(before, after), encoding='utf8', newline='')

def main():
    if OUT.exists():
        raise ValueError('Candidate exists; no overwrite')
    if core(BASE) != '1761a06deada9d851126d540d842bd55a49882fc6daf3d957873a651a91d53e8':
        raise ValueError('Frozen M68 identity changed')
    shutil.copytree(BASE/'ark_sim', OUT/'ark_sim', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Parent carries only this offline JSON fixture, never V1 runtime code.
    fixture = Path('ark_emulator/levels/packs/level_main_00-01.json')
    (OUT/fixture).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE/fixture, OUT/fixture)
    shutil.copyfile(Path(__file__).with_name('journal.py'), OUT/'ark_sim/kernel/journal.py')
    events = OUT/'ark_sim/kernel/events.py'
    replace(events, 'from .interning import PayloadInterner',
            'from .interning import PayloadInterner\nfrom .journal import DiskEventRecords')
    replace(events, '            self._next_id += 1\n            self._records.append(',
            '            self._records.append(')
    replace(events, '            return event_id', '            self._next_id += 1\n            return event_id')
    replace(events, '            payload = self._payload_interner.intern(payload)',
            '            if not isinstance(self._records, DiskEventRecords):\n                payload = self._payload_interner.intern(payload)')
    replace(events, '    def snapshot(self):\n        with self._lock:\n            return clone({"records": self._records, "next_id": self._next_id})',
'''    def enable_disk(self, path):
        with self._lock:
            records = DiskEventRecords(path)
            for record in self._records:
                records.append(record)
            self._records = records
            self._payload_interner.clear()

    def export_jsonl(self, path):
        with self._lock:
            if not isinstance(self._records, DiskEventRecords):
                raise RuntimeError("Direct byte export requires an enabled event journal")
            return self._records.export(path)

    def snapshot(self, event_reference=False):
        with self._lock:
            if event_reference:
                if not isinstance(self._records, DiskEventRecords):
                    raise RuntimeError("Event reference checkpoint requires an enabled journal")
                return {"reference": self._records.reference(), "next_id": self._next_id}
            return clone({"records": list(self._records), "next_id": self._next_id})''')
    replace(events, '            data = freeze_event_payload(data)\n            previous = 0',
'''            if "reference" in data:
                records = DiskEventRecords.from_reference(data["reference"])
                data = {"records": records, "next_id": data["next_id"]}
            else:
                data = freeze_event_payload(data)
                records = data["records"]
            previous = 0''')
    replace(events, '            self._records = [readonly({**dict(record), "payload": self._payload_interner.intern(record["payload"])}) for record in data["records"]]',
'''            self._records = records if isinstance(records, DiskEventRecords) else [readonly({**dict(record), "payload": self._payload_interner.intern(record["payload"])}) for record in records]''')
    replace(events, '            for record in data["records"]:\n',
            '            for record in data["records"]:\n                record = freeze_event_payload(record)\n')
    session = OUT/'ark_sim/kernel/session.py'
    replace(session, '    def checkpoint(self):', '''    def enable_event_journal(self, path):
        with self._lock:
            if self._advancing or self._atomic_depth:
                raise RuntimeError("Event storage can only change at an idle boundary")
            self._events.enable_disk(path)

    def export_events_jsonl(self, path):
        return self._events.export_jsonl(path)

    def checkpoint(self, event_reference=False):''')
    replace(session, '            return self._state_data()\n\n    def _state_data(self):',
            '            return self._state_data(event_reference)\n\n    def _state_data(self, event_reference=False):')
    replace(session, '"events": self._events.snapshot(), "random": self.random.snapshot(),',
            '"events": self._events.snapshot(event_reference), "random": self.random.snapshot(),')
    replace(session, 'for event in events.records):', 'for event in events._records):')
    replace(session, '            self._events._records, self._events._next_id = events._records, events._next_id',
            '            self._events._records, self._events._next_id = events._records, events._next_id\n            self._events._payload_interner.clear()')
    transaction = OUT/'ark_sim/kernel/transaction.py'
    replace(transaction, '    session._events._records.extend(events._records)\n', '')
    replace(transaction, '    # All validation happens above. Adoption cannot invoke user code or fail validation.',
            '    # Disk IO can fail: append/rollback the new batch before publishing stores.\n    session._events._records.extend(events._records)\n    # All validation happens above. Adoption cannot invoke user code or fail validation.')
    api = OUT/'ark_sim/adapters/api.py'
    replace(api, 'random_registry=None, random_algorithm=None):',
            'random_registry=None, random_algorithm=None, event_journal_path=None):')
    replace(api, '        self.ctx = RuntimeContext(program, self.session, providers)',
            '        if event_journal_path is not None:\n            self.session.enable_event_journal(event_journal_path)\n        self.ctx = RuntimeContext(program, self.session, providers)')
    replace(api, '    def checkpoint(self):', '    def checkpoint(self, event_reference=False):')
    replace(api, '"kernel": self.session.checkpoint(),', '"kernel": self.session.checkpoint(event_reference),')
    report = {'parent_core': core(BASE), 'core': core(OUT), 'source_sha256':
        {str(p.relative_to(OUT)): sha(p) for p in sorted((OUT/'ark_sim').rglob('*.py'))}}
    target = ROOT/'validation/campaign/m71_event_storage/composition.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps({'parent_core': report['parent_core'], 'core': report['core']}))

if __name__ == '__main__':
    main()
