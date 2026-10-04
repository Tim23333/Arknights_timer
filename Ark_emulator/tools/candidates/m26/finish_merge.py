"""Resolve inspected merge regions and wire qualification into pure queries."""
import json
import re
from pathlib import Path
from prepare_candidate import ROOT, OUT, REPORT, SOURCES, core, sha


def parts(text):
    pattern = re.compile(r'^<<<<<<< [^\n]+\n(.*?)^\|\|\|\|\|\|\| [^\n]+\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]+\n', re.M|re.S)
    return pattern


def main():
    initial = json.loads((REPORT/'merge_initial.json').read_bytes())
    changes = []
    for record in initial['conflicts']:
        relative = record['path']; path = OUT/'ark_sim'/relative; text = path.read_text(encoding='utf8')
        if sha(path) != next(r['result_sha256'] for r in initial['changes'] if r['path']==relative):
            raise ValueError('Unresolved merge bytes changed: '+relative)
        if relative == 'content/schemas.py':
            current, _, incoming = parts(text).search(text).groups()
            resolved = incoming.replace('"provider", "parameters"},', '"provider", "parameters", "eligible_rule"},', 1)
            resolved = resolved.replace('"behavior": {"provider"', '"behavior": {"decision", "provider"')
            text = parts(text).sub(lambda _: resolved, text)
        elif relative == 'domains/movement.py':
            current, _, incoming = parts(text).search(text).groups()
            resolved = incoming.replace('    def select(self, source, selector_id, ability=None, effect=None, primary=None):\n', current)
            text = parts(text).sub(lambda _: resolved, text)
            old = '        return ids\n\n    def select(self, source, selector_id, ability=None, effect=None, primary=None):'
            new = '        return [ref for ref in ids if self.qualifies(source, ref, definition, ability, effect)]\n\n    def select(self, source, selector_id, ability=None, effect=None, primary=None):'
            if text.count(old) != 1:
                raise ValueError('Pure eligibility return shape drift')
            text = text.replace(old, new)
        elif relative == 'domains/providers.py':
            text = parts(text).sub(lambda m: m.group(1)+m.group(3), text)
        elif relative == 'rules/contracts.json':
            # Catalog union by ID preserves each frozen definition exactly.
            base = json.loads((SOURCES['base'][0]/'ark_sim/rules/contracts.json').read_bytes())
            decision = json.loads((SOURCES['decision'][0]/'ark_sim/rules/contracts.json').read_bytes())
            eligibility = json.loads((SOURCES['eligibility'][0]/'ark_sim/rules/contracts.json').read_bytes())
            base_ids = {r['id'] for r in base['contracts']}
            added = [r for r in eligibility['contracts'] if r['id'] not in base_ids]
            existing = {r['id'] for r in decision['contracts']}
            if any(r['id'] in existing for r in added):
                raise ValueError('New contract ID collision')
            decision['contracts'].extend(added)
            text = json.dumps(decision, ensure_ascii=False, indent=2)+'\n'
        else:
            raise ValueError('Unreviewed conflict '+relative)
        if any(marker in text for marker in ('<<<<<<<', '|||||||', '>>>>>>>')):
            raise ValueError('Merge markers remain')
        path.write_text(text, encoding='utf8', newline='\n'); changes.append({'path': relative, 'sha256':sha(path)})
    current = core(OUT)
    for path, pin in SOURCES.values():
        if core(path) != pin:
            raise ValueError('Frozen parent drift')
    report = {'schema': 'ark-sim/decision-eligibility-resolution/v1', 'implementation': current,
              'source_cores': initial['source_cores'], 'changes': changes,
              'wiring': 'SpatialSystem.eligible applies the same pure qualifies filter as select, after geometry and before ordering/RNG',
              'formal_approved':False, 'actual_game_accuracy_verified':False}
    (REPORT/'merge_resolved.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({'implementation': current, 'resolved': len(changes)}))


if __name__ == '__main__':
    main()
