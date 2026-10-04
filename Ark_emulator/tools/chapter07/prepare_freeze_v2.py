"""Preserve first freeze failure; new output with required source archive directory."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter07/audit_and_freeze_source_v1.py';s=p.read_text().replace("OUT=ROOT/'validation/campaign/chapter07_sources_v1'","OUT=ROOT/'validation/campaign/chapter07_sources_v2'")
s=s.replace('OUT.mkdir(parents=True);invpath=',"OUT.mkdir(parents=True);(OUT/'source').mkdir();invpath=")
out=p.with_name('audit_and_freeze_source_v2.py');assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)
