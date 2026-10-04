"""CLI identities use the actual decoded bytes, including replacement races."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
import pytest

ROOT=Path(__file__).resolve().parents[3]


def test_comparator_changed_raw_input_between_decode_and_end_is_rejected(tmp_path):
    from tools.experiments.trace_comparison.test_comparison import fixture
    native,model,contract=fixture();paths=[]
    for name,value in [('native',native),('model',model),('contract',contract)]:
        p=tmp_path/(name+'.json');p.write_text(json.dumps(value),encoding='utf8');paths.append(p)
    original=Path.read_bytes;calls=0;changed=dict(native);changed['samples']=[];raw=json.dumps(changed).encode()
    def read(self):
        nonlocal calls
        if self.resolve()==paths[0].resolve():
            calls+=1
            if calls==1:return raw
        return original(self)
    out=tmp_path/'result.json';arguments=['compare','--native',str(paths[0]),'--model',str(paths[1]),'--contract',str(paths[2]),'--output',str(out)]
    with patch.object(sys,'argv',arguments),patch.object(Path,'read_bytes',read):
        with pytest.raises(ValueError,match='inputs changed'):runpy.run_path(str(ROOT/'tools/compare_campaign_trace.py'),run_name='__main__')
    assert not out.exists() and calls==2


def test_comparator_report_hashes_match_decoded_raw_bytes(tmp_path):
    from tools.experiments.trace_comparison.test_comparison import fixture
    paths=[]
    for name,value in zip(('native','model','contract'),fixture()):
        p=tmp_path/(name+'.json');p.write_text(json.dumps(value),encoding='utf8');paths.append(p)
    out=tmp_path/'result.json'
    with patch.object(sys,'argv',['compare','--native',str(paths[0]),'--model',str(paths[1]),'--contract',str(paths[2]),'--output',str(out)]):
        with pytest.raises(SystemExit) as ex:runpy.run_path(str(ROOT/'tools/compare_campaign_trace.py'),run_name='__main__')
    assert ex.value.code==0
    d=json.loads(out.read_bytes())
    assert d['decoded_input_sha256']=={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
