"""Preserve illegal scheduledEffects fixture; source battle effects use public schema."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter06_predefines/test_frost_consumer.py';s=p.read_text().replace('chapter06_predefined_consumer_v1','chapter06_predefined_consumer_v2').replace("{'at':100,'source':'trap_010_frosts#1','targets':['system/battle'],'effect':e}","{'at':100,'effect':e}");out=p.with_name('test_frost_consumer_v2.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)
