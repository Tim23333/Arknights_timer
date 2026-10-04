"""Read a full journal once to audit process/commands/base-life receipts."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    registry=json.loads((ROOT/'validation/campaign/runthrough/registry.json').read_bytes())
    entry=registry['cases'][args.case];report_path=ROOT/entry['report'];report=json.loads(report_path.read_bytes())
    package=json.loads((ROOT/entry['package']).read_bytes());commands=json.loads((ROOT/entry['commands']).read_bytes())
    assert report['passed'] and report['process_complete'] and report['identity_stable']
    assert report['checkpoint_equal'] and report['durable_checkpoint_equal'] and report['replay_equal']
    assert report['source_at_start']==report['source_at_completion'] and report['implementation']==entry['implementation']==report['core_at_completion']
    for name,pin in [(entry['package'],report['package_sha256']),(entry['commands'],report['commands_sha256'])]:
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==pin
    journal=Path(report['journal']['path']);journal=journal if journal.is_absolute() else ROOT/journal
    digest=hashlib.sha256();count=0;outcomes=[];losses=[];exits=[];finishes=[]
    with journal.open('rb') as file:
        for line in file:
            digest.update(line);count+=1
            if not any(token in line for token in (b'"lifecycle.leak_loss"',b'"entity.exited"',b'"scenario.finished"',b'"command.accepted"',b'"command.rejected"')):continue
            event=json.loads(line);kind=event['type'];payload=event['payload']
            if kind=='calculation' and payload.get('calculation_id')=='lifecycle.leak_loss':
                assert type(payload['value']) in (int,float) and payload['value']>=0
                losses.append({'event_id':event['id'],'tick':event['time'],'loss':payload['value'],'source':payload.get('source')})
            elif kind=='entity.exited':exits.append({'event_id':event['id'],'tick':event['time'],'target':payload.get('target')})
            elif kind=='scenario.finished':finishes.append(event)
            elif kind in ('command.accepted','command.rejected'):outcomes.append(event)
    assert count==report['journal']['events']==report['observations']['event_count']
    assert digest.hexdigest()==report['journal']['sha256']
    assert outcomes==report['commands'] and len(outcomes)==len(commands)
    for outcome,(_,command) in zip(outcomes,sorted(enumerate(commands),key=lambda pair:(pair[1]['at'],pair[0]))):
        action=dict(command);at=action.pop('at');assert outcome['time']==at and outcome['payload']['action']==action
    life=package['scenarioDraft']['metadata']['runthrough_profile']['base_life_resource']
    initial=package['scenarioDraft']['resources'][life]['initial'];total=sum(x['loss'] for x in losses)
    assert len(losses)==len(exits)==report['state']['leaks'] and initial-total==report['base_life_final']
    assert report['state']['finished'] and report['state']['pending_waves']==0 and report['state']['timeline']['phase']=='complete'
    assert report['actual_births']==report['expected_births'] and sum(report['actual_births'].values())==report['state']['kills']+report['state']['leaks']
    result={'schema':'ark-sim/completed-runthrough-file-audit/v1','case':args.case,'passed_full_process_evidence':True,
        'report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),'implementation':report['implementation'],
        'journal_sha256':digest.hexdigest(),'journal_events':count,'journal_bytes':journal.stat().st_size,'actual_outcomes':dict(Counter(e['type'] for e in outcomes)),
        'life_ledger':{'initial':initial,'final':report['base_life_final'],'sum':total,'losses':losses,'exits':exits},'finish_events':finishes,
        'pending_input_metadata_gaps_preserved':report['pending_model_gaps'],'scope':'Complete recorded process and exact persisted evidence; source/declared algorithm review is separate from this receipt',
        'actual_game_accuracy_verified':False,'whole_goal_complete':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'case':args.case,'passed_full_process_evidence':True,'events':count,'life':report['base_life_final'],'loss':total,'finish_events':len(finishes)}))


if __name__=='__main__':main()
