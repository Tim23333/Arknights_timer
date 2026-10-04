"""Keep saved observations exactly at the compared public replay boundary."""
from pathlib import Path
p=Path(__file__).with_name('verify_source_bound_v1.py')
s=p.read_text().replace("out = folder / 'source_bound_v1'","out = folder / 'source_bound_v2'")
s=s.replace("assert s.ctx.attributes.value('boss','atk') == 2240", "atk_events = [e for e in s.session.events if e['type'] == 'calculation' and e['payload'].get('calculation_id') == 'attributes.effective' and e['payload'].get('trace',{}).get('context',{}).get('attribute') == 'atk' and e['payload'].get('trace',{}).get('context',{}).get('owner_id') == s.session.world.resolve('boss')]\n    assert atk_events and atk_events[-1]['payload']['value'] == 2240")
s=s.replace("after = {str(p):sha(p) for p in guarded}", "assert s.snapshot() == restored.snapshot() == head.snapshot()\n    after = {str(p):sha(p) for p in guarded}")
p.with_name('verify_source_bound_v2.py').write_text(s,encoding='utf-8',newline='')
