"""Reproduce the v3 source converter with an explicit dormant hidden contract."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    source=ROOT/'tools/build_reference_stage_scenario_v2.py';assert hashlib.sha256(source.read_bytes()).hexdigest()=='f9a2814f444549e66839be0709dcce65284f4c8a7a2254b84ccdd59ceab787cb'
    text=source.read_text(encoding='utf8');old="                if record.get('hidden'):raise ValueError('Hidden predefined needs explicit dormant/visibility adapter')"
    new="""                if record.get('hidden'):
                    alias=record.get('alias')
                    if (not isinstance(alias,str) or not alias or match.get('active') is not False
                            or match.get('registration_key')!=alias or match.get('instanceAlias')!=alias):
                        raise ValueError('Hidden predefined requires exact alias and truly dormant registration')
                elif match.get('active',True) is not True:
                    raise ValueError('Visible predefined cannot be silently authored dormant')"""
    assert text.count(old)==1
    text=text.replace(old,new)
    # The native input/profile equality, exact record ordering, configuration,
    # position/facing and every other conversion check remains unchanged.
    out=ROOT/'tools/build_reference_stage_scenario_v3.py'
    with out.open('x',encoding='utf8',newline='') as f:f.write(text)
    print(hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
