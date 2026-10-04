"""Preserve fixture failures; use real branch schema and actual buff event key."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter06_predefines/test_frost_advanced_v1.py';s=p.read_text()
old="{'frstar_frosts':{'phases':[{'pre_delay':0,'effects':[{'at':0,'effect':{'op':'activate_predefined','target':'battle','parameters':{'key':a}}} for a in profile['exact_aliases']]}]}}"
new="{'frstar_frosts':{'loop':False,'phases':[{'pre_delay_seconds':0,'actions':[{'delay_seconds':0,'effects':[{'op':'activate_predefined','target':'battle','parameters':{'key':a}}]} for a in profile['exact_aliases']]}]}}"
assert s.count(old)==1;s=s.replace(old,new).replace("get('definition')=='buff/ch6/cold/e2c_cold'","get('buff')=='buff/ch6/cold/e2c_cold'");out=p.with_name('test_frost_advanced_v2.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)
