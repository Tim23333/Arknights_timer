"""Typed native visibility and globally unique predefine registration aliases."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    source=ROOT/'tools/build_reference_stage_scenario_v3.py';assert hashlib.sha256(source.read_bytes()).hexdigest()=='85017cfda3a47c707ee16e7608afdda711333a68a32d2c8e9c2c5ddb316a8386'
    text=source.read_text(encoding='utf8');old="        for bucket in ('characterInsts','tokenInsts'):\n            records=native['predefines'].get(bucket) or []"
    new="""        aliases=set()
        for bucket in ('characterInsts','tokenInsts'):
            for record in native['predefines'].get(bucket) or []:
                if type(record.get('hidden')) is not bool:
                    raise ValueError('Native predefined hidden flag must be strict boolean')
                alias=record.get('alias')
                if alias is not None:
                    if not isinstance(alias,str) or not alias or alias in aliases:
                        raise ValueError('Native predefined aliases must be globally unique nonempty strings')
                    aliases.add(alias)
        for bucket in ('characterInsts','tokenInsts'):
            records=native['predefines'].get(bucket) or []"""
    assert text.count(old)==2
    # Add once before the first source/profile population check. All later
    # record equality and position/configuration consumers remain untouched.
    text=text.replace(old,new,1)
    out=ROOT/'tools/build_reference_stage_scenario_v4.py'
    with out.open('x',encoding='utf8',newline='') as f:f.write(text)
    print(hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
