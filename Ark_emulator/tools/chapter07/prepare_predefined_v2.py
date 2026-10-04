"""New source-only variant using already frozen official mixed-version token assets."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];s=(ROOT/'tools/chapter07/build_predefined_sources.py').read_text()
s=s.replace("OUT = ROOT/'packages/campaign/chapter07_predefines/source.reference.json'","OUT = ROOT/'packages/campaign/chapter07_predefines/source.v2.reference.json'")
s=s.replace("if not paths and key == 'trap_010_frosts':","if not paths and key in ('trap_011_ore','trap_012_mine'):")
s=s.replace("Exact table-aligned token asset replaces this candidate and must be re-extracted","Frozen 20250327 token package is a replaceable mixed-version source. Fixed56aee tables/local20260831 assets remain separate and no version alignment is asserted.")
out=ROOT/'tools/chapter07/build_predefined_sources_v2.py';assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)
