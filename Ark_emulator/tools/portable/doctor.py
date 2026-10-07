"""Check paused handoff inputs and frozen source identities without simulation."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
EXPECTED = {
    'primary': (ROOT, '08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'),
    'head7': (REPO / 'unpack_work/campaign_campaign_foundation_v5_candidate', '82db6a9db5ddd3a4c3c58f05b04e773419312ae77d5fc086fbb98a7a984bf8ae'),
    'elemental94': (REPO / 'unpack_work/campaign_elemental_lease_v4_candidate', '94d2f5cfcc42f8845c6cb23643f1910aa94a78115a60d83813d0738df6db8c63'),
    'resources08': (REPO / 'unpack_work/campaign_resource_channel_v1_candidate', '08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878'),
    'phase': (REPO / 'unpack_work/campaign_owned_channel_phase_v2_candidate', 'da218736ae42600b5d80653b411508b13438e9002b18af3f04233285ac3cb226'),
    'indexed': (REPO / 'unpack_work/campaign_death_event_lookup_v1_candidate', '12e1e1adf291a505443980bca51046c725382d82fd458e4adbc4482bcf1b9183'),
    'callbacks': (REPO / 'unpack_work/campaign_owned_interrupt_callbacks_v1_candidate', '737e23225fd3c3b9f3d75d9f005a6a5f2ce4a28b0f29fd444276c805cca49e87'),
    'combined_draft': (REPO / 'unpack_work/campaign_owned_callbacks_indexed_v1_candidate', '0682991e26d74cf86e8445dd68d2a62cc600ceff2a526620d71360d0354ba67a'),
}


def core(runtime):
    folder = runtime / 'ark_sim'
    files = {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(folder.rglob('*.py'))}
    raw = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
    return hashlib.sha256(raw).hexdigest(), len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    cases = []
    for name, (runtime, expected) in EXPECTED.items():
        actual, files = core(runtime)
        cases.append({'name': name, 'path': str(runtime), 'expected': expected,
                      'actual': actual, 'python_source_files': files, 'passed': actual == expected})
    report = {'schema': 'ark-sim/portable-doctor/v1', 'passed': all(row['passed'] for row in cases),
              'runtime_checks': cases, 'python': sys.version, 'windows': os.name == 'nt',
              'task_status': 'paused', 'simulation_started': False,
              'fixed_log_drive_available': Path('E:/').exists(),
              'historical_absolute_paths': 'Provenance only; resolve through unpack_work/portable_state/legacy_paths.json when reading historical pins on a relocated checkout.',
              'identity_platform': 'Historical implementation digests contain Windows path separators. This handoff supports Windows/Python3.12; another OS requires fresh identities and verification.'}
    if args.output:
        if args.output.exists():
            raise FileExistsError('Preserve previous doctor receipt')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
