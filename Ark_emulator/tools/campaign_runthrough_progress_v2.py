"""Add real sealed-journal prefix verification to existing runthrough policy."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.campaign_runthrough_progress import build as original,inspect as original_inspect,ROOT,sha


def verify_reference(root,report):
    reference=report.get('checkpoint_event_reference')
    if reference is None:return None
    if not isinstance(reference,dict) or set(reference)!={'schema','path','sha256','bytes','count'} or reference['schema']!='ark-sim/event-journal-reference/v1':
        raise ValueError('Unknown sealed journal reference')
    if any(type(reference[k]) is not int or reference[k]<0 for k in ('bytes','count')):raise ValueError('Invalid journal reference integer metadata')
    pin=reference['sha256']
    if type(pin) is not str or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):raise ValueError('Invalid reference SHA256')
    path=Path(reference['path']);checkpoint=Path(report['checkpoint']);journal=Path(report['journal']['path'])
    if not path.is_absolute():raise ValueError('Reference path must be absolute')
    if not checkpoint.is_absolute():checkpoint=Path(root)/checkpoint
    if not journal.is_absolute():journal=Path(root)/journal
    saved=json.loads(checkpoint.read_bytes())
    if saved['kernel']['events']['reference']!=reference:raise ValueError('Actual main checkpoint/reference differs from report')
    if path.stat().st_size!=reference['bytes'] or sha(path)!=pin:raise ValueError('Actual sealed journal bytes differ')
    digest=hashlib.sha256();remaining=reference['bytes'];count=0
    with journal.open('rb') as full,path.open('rb') as sealed:
        for line in sealed:
            if not line.endswith(b'\n') or full.read(len(line))!=line:raise ValueError('Checkpoint is not exact complete-log prefix')
            digest.update(line);remaining-=len(line);count+=1
    if remaining!=0 or count!=reference['count'] or digest.hexdigest()!=pin:raise ValueError('Reference count/prefix digest differs')
    if count>report['observations']['event_count']:raise ValueError('Checkpoint prefix exceeds final events')
    return {'status':'verified','path':str(path),'sha256':pin,'bytes':reference['bytes'],'count':count,'exact_final_journal_prefix':True}


def inspect(root,entry):
    result=original_inspect(root,entry)
    if result['process_status'] not in ('complete','incomplete'):return result
    try:
        report=json.loads((Path(root)/entry['report']).read_bytes());proof=verify_reference(root,report)
        if proof is not None:result['sealed_checkpoint_journal']=proof
    except (KeyError,ValueError,TypeError,OSError) as error:
        result.update(process_status='stale_or_invalid',durable_checkpoint_status='pending',determinism_status='pending',reason=str(error))
    return result


def build(root=ROOT):
    root=Path(root);result=original(root);registry=json.loads((root/'validation/campaign/runthrough/registry.json').read_bytes())
    for row in result['cases']:
        entry=registry['cases'].get(row['native_id'])
        if entry:row.update(inspect(root,entry))
    result['schema']='ark-sim/campaign-runthrough-progress/v2'
    result['counts'].update(process_complete=sum(r['process_status']=='complete' for r in result['cases']),
        determinism_verified=sum(r['process_status']=='complete' and r['determinism_status']=='verified' for r in result['cases']),
        durable_checkpoint_verified=sum(r['process_status']=='complete' and r['durable_checkpoint_status']=='verified' for r in result['cases']))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();result=build()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(result['counts']))
