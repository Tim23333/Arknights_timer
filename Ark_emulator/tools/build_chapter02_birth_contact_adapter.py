"""Adapt frozen born timing to M41's explicit environment-contact protection."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'packages/campaign/chapter02_units/airdrp.birth.model.json'
SOURCE_SHA='8bbe5f24351458257886c14e1a5f0994660d8d879897395383d6cec4fea8d602'
OUT=ROOT/'packages/campaign/chapter02_units/airdrp.birth_contact.model.json'


def build():
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('Frozen airdrop born model drift')
    p=json.loads(raw)
    for buff in p['buffs']:
        if buff['duration_seconds']!=1.5 or buff['metadata'].get('declared_birth_phase') is not True:
            raise ValueError('Contact defer requires exact actual born phase')
        buff['contact_flags']={'defer_fall':True}
        buff['metadata']['contact_adapter']='M41 explicit half-open born protection; environment fall checked at45tick expiry; target-free/stun alone does not imply immunity.'
    p['manifest']['id']+='/contact_defer'
    p['manifest']['metadata'].update(birth_contact_builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parent_born_source_sha256=SOURCE_SHA,required_core_feature='tile.contact and buff.contact_flags.defer_fall',
        contact_source_policy='Reference appearance-completion fall check after actual1.5second birth; no source stat or birth clock changes.')
    return p


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    p=build();raw=(json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    if args.check:
        if OUT.read_bytes()!=raw:raise ValueError('Born contact adapter changed')
    else:OUT.write_bytes(raw)
    print(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'unit_count':len(p['entities']),'stat_changes':False}))
