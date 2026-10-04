import copy,hashlib,importlib.util,json,threading,time
from pathlib import Path
import pytest
from ark_sim import Compiler,Engine
from ark_sim.contracts import thaw
from ark_sim.kernel.events import EventLog
ROOT=Path(__file__).resolve().parents[3]
HELPER=ROOT/'tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py'
spec=importlib.util.spec_from_file_location('root_v14',HELPER);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


def make(tmp):
    p={'manifest':{'requires':['preset/ark_standard']},'entities':[{'id':'unit/observer','kind':'entity','tags':['player'],
        'components':{'resources':{'zeta':{'initial':0,'capacity':100,'recovery_rate':30},'alpha':{'initial':0,'capacity':100,'recovery_rate':60}}}}],
        'scenarioDraft':{'id':'scene/rootstorage','ruleset':'ruleset/ark_standard','objectives':{},'map':{'rows':1,'cols':1},
            'initialEntities':[{'definition':'unit/observer','instanceAlias':'u','position':{'row':0,'col':0}}]}}
    return Engine.create(Compiler().compile(p),seed=77099,event_journal_path=tmp/'active.jsonl')


def digest(value):return hashlib.sha256(json.dumps(thaw(value),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def test_actual_observation_lock_blocks_legal_advance_until_complete_boundary(tmp_path,monkeypatch):
    s=make(tmp_path);s.advance(3);expected=digest(s.snapshot());original=s.session.export_events_jsonl
    attempted=threading.Event();finished=threading.Event();workers=[]
    def export(path):
        output=original(path)
        def advance():attempted.set();s.advance(1);finished.set()
        thread=threading.Thread(target=advance);workers.append(thread);thread.start();assert attempted.wait(1)
        assert not finished.wait(.1)
        return output
    monkeypatch.setattr(s.session,'export_events_jsonl',export)
    observed=helper.observations(s,tmp_path/'observed.jsonl')
    assert observed['snapshot']==expected
    for thread in workers:thread.join(3);assert not thread.is_alive()
    assert finished.is_set() and s.session.time==4


def test_forged_export_bytes_and_matching_hash_header_still_rejected_by_owned_rows(tmp_path,monkeypatch):
    s=make(tmp_path);original=s.session.export_events_jsonl
    def export(path):
        output=original(path);raw=Path(path).read_bytes();changed=raw.replace(b'"time":0',b'"time":1',1);assert changed!=raw
        Path(path).write_bytes(changed);return {**output,'sha256':hashlib.sha256(changed).hexdigest(),'bytes':len(changed)}
    monkeypatch.setattr(s.session,'export_events_jsonl',export)
    with pytest.raises(ValueError):helper.observations(s,tmp_path/'forged.jsonl')


@pytest.mark.parametrize('value',[True,1.0,-1,'1',None])
def test_count_wrong_type_reference_cannot_restore(value,tmp_path):
    s=make(tmp_path);cp=s.checkpoint(event_reference=True);cp['kernel']['events']['reference']['count']=value
    with pytest.raises(ValueError):Engine.restore(s.program,cp)


def test_reference_duplicate_json_member_names_do_not_silently_restore(tmp_path):
    log=EventLog();log.enable_disk(tmp_path/'one.jsonl');log.emit('probe',{},0);cp=log.snapshot(event_reference=True)
    path=Path(cp['reference']['path']);raw=path.read_bytes();changed=raw.replace(b'"time":0',b'"time":9,"time":0');assert raw!=changed
    path.write_bytes(changed);cp['reference'].update(sha256=hashlib.sha256(changed).hexdigest(),bytes=len(changed))
    with pytest.raises(ValueError):EventLog().restore(cp)


def test_ordered_published_checkpoint_restores_exact_resource_event_order(tmp_path):
    s=make(tmp_path);s.advance(3);meta=helper.write_checkpoint(s,tmp_path/'main.json');cp=helper.load_checkpoint(meta)
    assert list(cp['kernel']['world']['entities'][1]['components']['resources'])==['zeta','alpha']
    r=Engine.restore(s.program,cp);s.advance(5);r.advance(5)
    assert s.snapshot()==r.snapshot()
