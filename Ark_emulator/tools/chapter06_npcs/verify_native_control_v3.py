"""Use original native control subset verifier with repaired content identity."""
import hashlib,json,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tools/chapter06_npcs/verify_native_control_subset_v2.py'


def main():
    text=SOURCE.read_text(encoding='utf8')
    old="from tools.chapter06_npcs.amiya_policy import providers"
    new="from tools.chapter06_npcs.providers_v2 import providers"
    assert text.count(old)==1;text=text.replace(old,new)
    assert text.count("'huang.model.json'")==1;text=text.replace("'huang.model.json'","'huang.v7.model.json'")
    oldout="chapter06_native_controls_subset_v2"
    assert oldout in text;text=text.replace(oldout,'chapter06_native_controls_subset_v3')
    before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    ns={'__name__':'current_native_control_v3','__file__':str(SOURCE)}
    exec(compile(text,str(SOURCE),'exec'),ns);ns['main']()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==before
    out=ROOT/'validation/campaign/chapter06_native_controls_subset_v3/wrapper_identity.json'
    out.write_text(json.dumps({'original_verifier_sha':before,'wrapper_sha':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'substitutions':['explicit composed providers','huang.v7.model.json','new output directory'],
        'original_expected_values_unchanged':True,'whole_stage_executed':False},indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
