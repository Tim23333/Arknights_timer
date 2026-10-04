from tools.experiments.m50_peer.test_stock import *
from ark_sim.adapters.api import implementation_digest
from ark_sim.contracts import thaw
import hashlib
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def main():
    core=implementation_digest();out=ROOT/'validation/campaign/m50_peer';out.mkdir(exist_ok=True)
    s=make();plan=prepare(s.ctx,'unit/widget',{'row':0,'col':0});s.submit(command(0),at=0);s.advance(1);first=s.checkpoint();tickets=s.ctx.resources.current('system/battle','tickets')
    with s.session.atomic():record(s.ctx,'widget0',plan)
    write(out/'duplicate_record_first.json',first);write(out/'duplicate_record_second.json',s.checkpoint());write(out/'duplicate_plan.json',plan)
    repeated={'before_tickets':tickets,'after_tickets':s.ctx.resources.current('system/battle','tickets'),'actors':len(s.session.world.entities()),'expected':'repeat record rejects and leaves stock unchanged','scope':'direct internal record boundary explicitly requested by Root; not a second public deployment'}
    p=fixture();p['rules']=[{'id':'rule/dp_floor','kind':'rule','contract':'resource.bounds','parameters':{'floor':3},'implementation':{'type':'provider','provider':'peer.floor'}}]
    p['scenarioDraft']['resources']['dp'].update(initial=4,bounds_rule='rule/dp_floor');s=make(p);commands=[{**command(0),'at':0}];s.submit(command(0),at=0);s.advance(1)
    for name,value in [('partial_dp_input.json',p),('partial_dp_commands.json',commands),('partial_dp_replay.json',s.export_replay()),('partial_dp_final.json',s.snapshot())]:write(out/name,value)
    partial={'initial_dp':4,'after_dp':s.ctx.resources.current('system/battle','dp'),'actual_paid':4-s.ctx.resources.current('system/battle','dp'),
        'stored_paid_cost':s.ctx.get('widget0',('deployable','paid_cost')),'tickets':s.ctx.resources.current('system/battle','tickets'),
        'commands':[thaw(e) for e in s.session.events if e['type'].startswith('command.')],'expected':'partial DP payment rejects and rolls entire command back',
        'scope':'existing public deployment adjust path inherited from a829, exposed with separate finite stock; ordinary default bounds not claimed affected'}
    assert core==implementation_digest()
    names=['tools/experiments/m50_peer/test_stock.py',str(Path(__file__).relative_to(ROOT)),'../unpack_work/campaign_m50_deploy_stock_candidate/ark_sim/domains/deployment.py','../unpack_work/campaign_m50_deploy_stock_candidate/ark_sim/adapters/api.py']
    report={'schema':'ark-sim/independent-payment-counterexamples/v1','status':'actual_duplicate_record_and_partial_DP_failures','core_before':core,'core_after':implementation_digest(),
        'source_locks':{x:sha(ROOT/x) for x in names},'actual_module':sys.modules['ark_sim'].__file__,'duplicate_record':repeated,'partial_DP':partial,
        'fixture_errors_preserved':'Bounds accepts provider only; initial expression/graph fixtures and missing overflow provider result logged separately and corrected before these actual observations.',
        'actual_client_verified':False,'formal_approved':False}
    write(out/'original_failures.json',report);print(json.dumps({'core':core,'report_sha256':sha(out/'original_failures.json'),'repeated':repeated,'partial':{k:partial[k] for k in ('actual_paid','stored_paid_cost')}}))
if __name__=='__main__':main()
