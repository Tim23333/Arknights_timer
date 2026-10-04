"""Verify the complete controlled Boss capture without loading gigabytes into RAM."""
import codecs
import hashlib
import json
import mmap
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ACT=ROOT/'validation/campaign/chapter08_bsnake_full_actual_v1'
OUT=ROOT/'validation/campaign/chapter08_bsnake_full_source_audit_v2'


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def events(path):
    marker=b',"events":[{"id":1,'
    with path.open('rb') as stream:
        with mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as mapped:
            offset=mapped.find(marker)
            assert offset>=0,'Expected exact top-level compact event array marker'
            assert mapped.find(marker,offset+len(marker))<0,'Ambiguous event array marker'
        stream.seek(offset+len(b',"events":['))
        text='';decode=codecs.getincrementaldecoder('utf8')();parser=json.JSONDecoder()
        eof=False
        while True:
            text=text.lstrip(', \r\n\t')
            if text.startswith(']'):return
            try:
                event,end=parser.raw_decode(text)
            except json.JSONDecodeError:
                if eof:raise ValueError('Truncated complete capture')
                block=stream.read(1024*1024);eof=not block
                text+=decode.decode(block,final=eof)
                continue
            yield event
            text=text[end:]


def main():
    assert not OUT.exists()
    proof=json.loads((ACT/'verification.json').read_bytes())
    assert proof['passed'] and proof['waiting200_and_terminal4900_and_public_head_equal'] and proof['guards_equal']
    chosen={'source.bsnake.screen.volley','projectile.launched','damage.accepted','ability.started',
            'branch.phase_started','timeline.source_transferred','timeline.finish_requested','command.accepted'}
    selected=[];count=0;last_time=0
    for event in events(ACT/'forward.capture.json'):
        count+=1
        assert event['id']==count and type(event['time']) is int and event['time']>=last_time
        last_time=event['time']
        if event['type'] in chosen:selected.append(event)
    assert count==proof['events']==160692
    boss=20;fire='ability/ch8/bsnake/firecommon'
    rows=lambda kind:[event for event in selected if event['type']==kind]
    volleys=rows('source.bsnake.screen.volley')
    assert [event['time'] for event in volleys]==[207+60*n for n in range(1,11)]+[4650+60*n for n in range(1,11)]
    rays=[event for event in rows('projectile.launched') if event['payload']['source']==boss and event['payload']['ability']==fire]
    hits=[event for event in rows('damage.accepted') if event['payload']['source']==boss and event['payload']['ability']==fire]
    assert len(rays)==len(hits)==140
    assert sorted(Counter(event['payload']['definition'] for event in rays).values())==[20]*7
    assert sum(event['time']<1047 for event in rays)==70
    for target,res in zip(range(13,20),[17,37,53,73,17,37,53]):
        actual=[event for event in hits if event['payload']['target']==target];assert len(actual)==20
        for event in actual:
            atk=1155 if event['time']<5490 else 770
            assert abs(event['payload']['amount']-atk*(1-res/100))<1e-9
    ordinary=[event for event in rows('ability.started') if event['payload']['source']==boss and any('/'+name+'/' in event['payload']['ability'] for name in ('normal','ignite','explode'))]
    assert not any(207<=event['time']<1047 or 4650<=event['time']<5490 for event in ordinary)
    summons=[event for event in rows('ability.started') if event['payload']['source']==boss and event['payload']['ability']=='ability/ch8/bsnake/summon_flame']
    assert [event['time'] for event in summons]==[3297]
    branches=rows('branch.phase_started');assert branches[0]['time']==3324 and branches[0]['payload']['actions']==5
    devices=[event for event in rows('ability.started') if event['payload']['ability']=='ability/ch8/flame/explode']
    assert len(devices)==5 and all(event['time']==4074 for event in devices)
    assert [(event['time'],event['payload']['parameters']['track_source_at_next_wave']) for event in rows('timeline.finish_requested')]==[(57,True),(4500,False)]
    assert [(event['time'],event['payload']['source']) for event in rows('timeline.source_transferred')]==[(117,boss)]
    assert len(rows('command.accepted'))==2
    captures={name:sha(ACT/(name+'.capture.json')) for name in ('forward','restored','head')}
    assert len(set(captures.values()))==1
    guard=json.loads((ACT/'guards.before.json').read_bytes())
    for path,pin in guard.items():assert sha(path)==pin,path
    OUT.mkdir()
    result={'passed':True,'core':proof['core'],'events':count,'capture_hashes':captures,'guard_pins_equal':True,
        'rays':140,'actual_screen_hits':140,'volley_times':[event['time'] for event in volleys],
        'summon_times':[3297],'branch_times':[3324],'five_devices_real25SP_cast_time':4074,
        'first_restoration_policy':'Reference full effective capacity75000; original raw recharge.5 retained, native mapping unresolved',
        'four_mode_CP_and_head_equal':True,'source_wave_transfer_same_actor':True,
        'scope':'Complete controlled source two public defeats with source stats, seven rows/ten volleys twice and one source Summon. Not44-birth whole or native renderer/client proof; normal qualified-target suppression remains separate probe.',
        'client_verified':False,'raw_retention':'Temporary captures may now be deleted after this compact numerical receipt'}
    target=OUT/'verification.json';target.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'passed':True,'sha':sha(target),'events':count,'rays':140}))


if __name__=='__main__':main()
