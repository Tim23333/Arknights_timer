"""Actual original-V3 SP calculations; no inference substituted for observed values."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'validation/campaign/m94_complete_c4'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 original=OUT/'full49_v3.original.json';receipt=json.loads(original.read_bytes());journal=Path(receipt['journal']['path']);assert sha(journal)==receipt['journal']['sha256'];source=None;events=[];calc=[];types={}
 with journal.open(encoding='utf8') as f:
  for line in f:
   e=json.loads(line);p=e['payload']
   if e['type']=='command.accepted' and p['action'].get('alias')=='c409_plosis':source=p['result']
   if source is None or not 1950<=e['time']<=2310:continue
   if e['type']=='calculation' and p.get('source')==source:
    name=p.get('calculation_id');types[name]=types.get(name,0)+1
    if name=='resource.recovery' or (name and 'attribute' in name and ('sp_recovery_rate' in str(p) or e['time'] in (1950,2220,2250))) or (name and 'buff.applicability' in name):calc.append(e)
   elif p.get('source')==source or p.get('target')==source or p.get('entity')==source:events.append(e)
   elif e['type'].startswith('command.') and p['action'].get('source')=='c409_plosis':events.append(e)
 assert source is not None
 report={'source_original_receipt':str(original),'original_receipt_sha':sha(original),'sealed_journal':receipt['journal'],'source_actor':source,'window':[1950,2310],'calculation_types':types,'actual_calculations':calc,'actual_events':events,'no_synthetic_calls_or_new_events':True,'prior95_statement':'Unverified rate1 arithmetic, explicitly corrected. Actual values are the calculation/resource records below.','whole_client_accuracy_claim':False}
 dest=OUT/'plosis_actual_v3.json'
 if dest.exists():raise ValueError('Preserve actual extraction')
 dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps({'source_actor':source,'calculation_types':types,'selected_calculations':len(calc),'selected_events':len(events),'report_sha':sha(dest)}))
if __name__=='__main__':main()
