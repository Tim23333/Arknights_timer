"""Read a fixed actual journal prefix without modifying its active writer."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--commands', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    digest = hashlib.sha256()
    rows = []
    bound = args.journal.stat().st_size
    final_id = final_tick = 0
    consumed = 0
    with args.journal.open('rb') as stream:
        while stream.tell() < bound:
            line = stream.readline()
            if not line or not line.endswith(b'\n') or stream.tell() > bound:
                break
            consumed += len(line)
            digest.update(line)
            # Full formula payloads remain in the original journal. Only public
            # command outcomes are decoded by this prefix observation tool.
            if b'"type":"command.accepted"' in line or b'"type":"command.rejected"' in line:
                event = json.loads(line)
                rows.append(event)
            # Parse the last line only after the immutable read bound is met.
            last = line
    if consumed:
        event = json.loads(last)
        final_id, final_tick = event['id'], event['time']
    deploys = [e for e in rows if e['type'] == 'command.accepted'
               and e['payload']['action']['action'] == 'deploy']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        'journal': str(args.journal.resolve()), 'prefix_bytes': consumed,
        'prefix_sha256': digest.hexdigest(), 'last_event_id': final_id,
        'last_tick': final_tick, 'commands_sha256': hashlib.sha256(args.commands.read_bytes()).hexdigest(),
        'actual_commands': rows,
        'distinct_accepted_deployments': sorted({e['payload']['action']['entity'] for e in deploys}),
        'full_process_complete': False, 'numeric_accuracy_verified': False,
        'scope': 'Actual public command outcomes in a fixed byte prefix; stage completeness and source identity must be checked separately.'
    }, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'last_tick': final_tick, 'commands': len(rows),
                      'accepted_deployments': len(deploys), 'sha': hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
