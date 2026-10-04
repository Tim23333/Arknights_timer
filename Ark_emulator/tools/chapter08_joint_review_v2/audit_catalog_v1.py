import sys,json,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[2];RUNTIME=ROOT.parent/'unpack_work/campaign_chapter08_joint_v2_candidate';BASE=ROOT.parent/'unpack_work/campaign_behavior_restart_clock_v2_candidate';LIFE=ROOT.parent/'unpack_work/campaign_buff_lifetime_v8_candidate';sys.path.insert(0,str(RUNTIME));sys.path.append(str(ROOT))
from ark_sim.rules.catalog import load_catalog,check_type
from ark_sim.contracts import thaw
from ark_sim.adapters.api import implementation_digest
OUT=ROOT/'validation/campaign/chapter08_catalog_independent_v1';OUT.mkdir(exist_ok=False);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=[BASE/'ark_sim/rules/contracts.json',LIFE/'ark_sim/rules/contracts.json',RUNTIME/'ark_sim/rules/contracts.json',ROOT/'tests_v2/test_rules.py',Path(__file__)]+[p for p in (RUNTIME/'ark_sim').rglob('*') if p.suffix in ('.py','.json')]
def guards():return {str(p):sha(p) for p in sorted(set(paths))}
def exact(a,b):
 if type(a)!=type(b):return False
 if isinstance(a,dict):return a.keys()==b.keys() and all(exact(a[k],b[k]) for k in a)
 if isinstance(a,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
 return a==b
before=guards();a=json.loads(paths[0].read_bytes());b=json.loads(paths[1].read_bytes());c=json.loads(paths[2].read_bytes());assert implementation_digest()=='a6ca7396556624768da2f83680ae34ad632d36dfa85f646916edbd1ee85f0128'
assert len(a['contracts'])==98 and len(c['contracts'])==99 and exact(c,b) and exact(c['contracts'][:98],a['contracts'])
for key in a:
 if key!='contracts':assert exact(a[key],c[key]),key
added=c['contracts'][98];assert added['id']=='buff.lifetime_rate' and added['owner']=='target' and added['contractVersion']==1 and added['outputSchema']=={'type':'number'}
assert added['implementations']==['expression','graph','provider'] and added['pureEvaluation'] is True and added['writesStateDirectly'] is False and added['versionsRequired'] is True
assert [x['name'] for x in added['inputs']]==['owner','source','instance','clock','attributes','parameters'] and all(x['required'] is True for x in added['inputs'])
catalog=load_catalog();snapshot=thaw(catalog);mutations=[]
for label,operation in [('outer',lambda:catalog.__setitem__('types',{})),('contract',lambda:catalog['contracts']['buff.lifetime_rate'].__setitem__('owner','source')),('input',lambda:catalog['contracts']['buff.lifetime_rate']['inputs'][0].__setitem__('required',False)),('input_sequence',lambda:catalog['contracts']['buff.lifetime_rate']['inputs'].append({})),('output_schema',lambda:catalog['contracts']['buff.lifetime_rate']['outputSchema'].__setitem__('type','boolean'))]:
 try:operation()
 except (TypeError,AttributeError):mutations.append(label)
 else:raise AssertionError('Catalog mutation accepted: '+label)
assert exact(thaw(catalog),snapshot)
custom=deepcopy(c);detached=load_catalog(custom);custom['contracts'][98]['inputs'][0]['required']=False;assert detached['contracts']['buff.lifetime_rate']['inputs'][0]['required'] is True
check_type(1,added['outputSchema']);invalid=[]
for value in (True,False,None,'1',float('nan'),float('inf')):
 try:check_type(value,added['outputSchema'])
 except Exception:invalid.append(repr(value))
 else:raise AssertionError('Invalidnumber output accepted')
after=guards();assert before==after
r={'passed':True,'core':implementation_digest(),'base98_catalog_sha':sha(paths[0]),'be1_catalog_sha':sha(paths[1]),'a6_catalog_sha':sha(paths[2]),'old98_type_exact':True,'only_added_contract':added,'all_noncontract_metadata_type_exact':True,'be1_a6_catalog_exact':True,'immutable_mutations_rejected':mutations,'caller_input_detached':True,'output_schema_nonfinite_bool_and_nonnumber_rejected':invalid,'scope':'Independentcatalog structural/immutability audit only. Existingtest expects98 but actual99 is exactly98prior+buff.lifetime_rate; doesnot turn oldfullsuite countfail into pass. Nonnegative lifetime semantic remainsdomainrate check separately proved by generic26; catalog number alone isnot falselyclaimed nonnegative. tests_v2 bytes guarded and notmodified.','guards_start':before,'guards_end':after,'guards_equal':True};(OUT/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(sha(OUT/'verification.json'))
