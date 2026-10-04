"""New all-referenced Buff row inventory; preserve exact loadFromDB semantics."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];p=ROOT/'tools/chapter07/decode_buff_sources.py';s=p.read_text();s=s.replace('buff.typed.reference.json','buff.all_referenced.v2.reference.json').replace("if v.get('loadFromDB') is True and v.get('buffKey'):keys.add(v['buffKey'])","if v.get('buffKey'):keys.add(v['buffKey'])")
s=s.replace("'required_keys':sorted(keys)","'reference_policy':'All inline buffKey IDs are queried as additional table evidence; native loadFromDB0 remains inline and is never changed into DB lookup. Missing table rows for inline definitions are source differences/pending, not guessed empty Buffs.','required_keys':sorted(keys)")
out=ROOT/'tools/chapter07/decode_buff_sources_v2.py';assert not out.exists();out.write_text(s,encoding='utf8',newline='');print(out)
