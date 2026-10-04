"""Exact current-module fixtures, no pytest reload monkeypatch ambiguity."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DIR=ROOT/'tools/chapter06_predefines'
s=(DIR/'test_frost_consumer_v3.py').read_text().replace('chapter06_predefined_consumer_v3','chapter06_predefined_consumer_final_v3').replace('module.reference.json','module.v2.reference.json');out=DIR/'test_frost_consumer_final_v3.py';assert not out.exists();out.write_text(s,encoding='utf8',newline='')
a=(DIR/'test_frost_advanced_v2.py').read_text().replace('test_frost_consumer_v3','test_frost_consumer_final_v3');out=DIR/'test_frost_advanced_final_v3.py';assert not out.exists();out.write_text(a,encoding='utf8',newline='')
r=(DIR/'verify_frost_final_v2.py').read_text().replace('chapter06_predefined_consumer_final_v2','chapter06_predefined_consumer_final_v3').replace('test_frost_consumer_v3','test_frost_consumer_final_v3').replace('test_frost_advanced_v2','test_frost_advanced_final_v3');out=DIR/'verify_frost_final_v3.py';assert not out.exists();out.write_text(r,encoding='utf8',newline='');print('Fresh declared module/OUT fixtures; assertions unchanged, old failed proof preserved')
