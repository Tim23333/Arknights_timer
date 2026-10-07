"""One frozen post-phase successor: exact indexed death event lookup only."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'validation/campaign/campaign_owned_channel_phase_v2/freeze.functional.v2.json'
PARENT_SHA='01856e38162f8c274e9186f6bee39a06b9f94c32ef26197b1f278e21dd7405cb'
OUT=ROOT.parent/'unpack_work/campaign_death_event_lookup_v1_candidate'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert sha(PARENT)==PARENT_SHA;lock=json.loads(PARENT.read_bytes());assert lock['core']=='da218736ae42600b5d80653b411508b13438e9002b18af3f04233285ac3cb226'
    parent=Path(lock['candidate']);inventory=lock['inventory'];assert all(sha(parent/k)==h for k,h in inventory.items())
    assert not OUT.exists(),'Preserve existing performance candidate'
    for name,h in inventory.items():
        p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((parent/name).read_bytes())
    target=OUT/'ark_sim/domains/death_spawns.py';text=target.read_text(encoding='utf8')
    old="    def event(self,event_id):\n        found=[e for e in self.ctx.session.events if e['id']==event_id]\n        if len(found)!=1:raise ValueError('Death spawn causal event unavailable')\n        return found[0]\n"
    new="    def event(self,event_id):\n        if type(event_id) is not int or event_id < 1:\n            raise ValueError('Death spawn event requires a strict positive integer ID')\n        records = self.ctx.session._events._records\n        if event_id > len(records):\n            raise ValueError('Death spawn causal event unavailable')\n        record = records[event_id - 1]\n        if (not isinstance(record, Mapping) or type(record.get('id')) is not int or\n                record['id'] != event_id or type(record.get('type')) is not str or not record['type']):\n            raise ValueError('Death spawn causal event identity/type invalid')\n        return record\n"
    assert text.count(old)==1,'Exact parent lookup source drift'
    target.write_bytes(text.replace(old,new,1).encode('utf8'))
    changed=[k for k in inventory if sha(OUT/k)!=inventory[k]];assert changed==['ark_sim/domains/death_spawns.py']
    assert all(sha(parent/k)==h for k,h in inventory.items())
    record={'schema':'ark-sim/death-event-indexed-candidate/v1','candidate':str(OUT),'parent':str(parent),'parent_core':lock['core'],
      'parent_freeze_sha256':PARENT_SHA,'delta':{'file':changed[0],'parent':inventory[changed[0]],'current':sha(target)},
      'inventory':{k:sha(OUT/k) for k in inventory},'scope':'Indexed actual contiguous event ID lookup only; no event content, sequencing, context, value or cause change for valid IDs.',
      'primary_modified':False,'live_source_modified':False,'passed':False,'gates_pending':True}
    dest=ROOT/'validation/campaign/campaign_death_event_lookup_v1';dest.mkdir(parents=True,exist_ok=True);(dest/'candidate.v1.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'candidate':str(OUT),'changed':changed,'delta_sha256':sha(target)}))
if __name__=='__main__':main()
