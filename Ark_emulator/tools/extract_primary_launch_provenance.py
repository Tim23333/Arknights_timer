"""Extract only this task's actual primary-suite launch and terminal tool records."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = Path(r'C:\Users\32134\.codex\sessions\2026\10\01\rollout-2026-10-01T15-03-01-01a0f646-1008-7372-a9c3-df5115f77689.jsonl')
LAUNCH = 'call_mX7JqYNT7P99E6qucKhU8fa3'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def outputs(payload):
    values = []
    for item in payload.get('output',[]):
        if item.get('type') == 'input_text':
            try:
                values.append(json.loads(item['text']))
            except json.JSONDecodeError:
                pass
    return values


def main():
    calls,responses = {},{}
    with TRANSCRIPT.open('rb') as stream:
        for index,line in enumerate(stream,1):
            if b'custom_tool_call' not in line:
                continue
            record = json.loads(line);payload = record.get('payload',{})
            uid = payload.get('call_id')
            source = payload.get('input',payload.get('arguments',''))
            if payload.get('type') == 'custom_tool_call':
                if uid == LAUNCH or (source.startswith('text(await tools.write_stdin({session_id:79422,')
                    and 'tools/record_primary_suite.py' in source):
                    calls[uid] = {'line_number':index,'record_sha256':digest(line),'record':record}
            elif payload.get('type') == 'custom_tool_call_output' and uid in calls:
                responses[uid] = {'line_number':index,'record_sha256':digest(line),'record':record}
    launch = calls[LAUNCH];response = responses[LAUNCH]
    source = launch['record']['payload']['input']
    assert "$env:CAMPAIGN_MECHANISM_PACKAGE=(Join-Path (Get-Location) 'packages/campaign/mainline_models/level_main_00-10.m12_projection.json')" in source
    assert '$env:CAMPAIGN_SUMMON_PACKAGE=$env:CAMPAIGN_MECHANISM_PACKAGE' in source
    assert '$env:ARKSIM_M10_REVIEW_ROOT=(Get-Location).Path' in source
    assert '-- tests_v2 -q' in source
    assert any(v.get('session_id') == 79422 for v in outputs(response['record']['payload']))
    completions = []
    for uid,call in calls.items():
        if uid == LAUNCH or uid not in responses:
            continue
        result = outputs(responses[uid]['record']['payload'])
        if result and result[0].get('exit_code') == 0 and 'session_id' not in result[0]:
            completions.append({'call':call,'response':responses[uid]})
    assert len(completions) == 1
    result = {'schema':'ark-sim/actual-suite-launch-provenance/v1','passed':True,
        'source_transcript':str(TRANSCRIPT),'thread_id':'01a0f646-1008-7372-a9c3-df5115f77689',
        'launch':launch,'launch_response':response,'terminal_poll':completions[0],
        'actual_shell_session':79422,'environment_assignments_verified_from_actual_launch':True,
        'environment':{'CAMPAIGN_MECHANISM_PACKAGE':'packages/campaign/mainline_models/level_main_00-10.m12_projection.json',
            'CAMPAIGN_SUMMON_PACKAGE':'packages/campaign/mainline_models/level_main_00-10.m12_projection.json',
            'ARKSIM_M10_REVIEW_ROOT':str(ROOT)},
        'scope':'Exact supervised shell invocation and matching returned handle/terminal result; no in-process environment instrumentation claim',
        'formal_approval':False}
    output = ROOT/'validation/campaign/m12_primary_launch_provenance_20261002.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'passed':True,'launch_call_id':LAUNCH,'session_id':79422,'output':str(output)}))


if __name__ == '__main__':
    main()
