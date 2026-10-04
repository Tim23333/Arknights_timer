"""Prepare a generic lossless numerical damage-request field transform."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m38_integrated_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m43_request_transform_candidate'
PROVIDER='''"""Pure request transform; unchanged fields retain their exact JSON values."""
import math
from collections.abc import Mapping
from ark_sim.contracts import thaw

def request_field_transform(inputs,params,context):
    request=inputs['effect']
    if not isinstance(request,Mapping):raise ValueError('request transform requires an effect mapping')
    if set(params)!={'field','factor','default'}:raise ValueError('request transform requires explicit field/factor/default')
    field=params['field'];factor=params['factor'];default=params['default']
    if not isinstance(field,str) or not field or field.startswith('_'):raise ValueError('request transform field must be a public key')
    for label,value in [('factor',factor),('default',default),('operand',request.get(field,default))]:
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('request transform '+label+' must be finite numeric')
    result=thaw(request);value=request.get(field,default)*factor
    if not math.isfinite(value):raise ValueError('request transform result must be finite')
    result[field]=value
    return {'accepted':True,'effect':result,'effects':[]}
'''


def main():
    if OUT.exists():raise ValueError('Candidate path already exists; frozen identity cannot be overwritten')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (OUT/'ark_sim/domains/request_transforms.py').write_text(PROVIDER,encoding='utf8',newline='\n')
    path=OUT/'ark_sim/domains/providers.py';text=path.read_text(encoding='utf8')
    text=text.replace('from .selection import eligibility_profile','from .selection import eligibility_profile\nfrom .request_transforms import request_field_transform')
    text=text.replace('BUILTIN_PROVIDERS = {','BUILTIN_PROVIDERS = {\n    "model.damage.request_field_transform": request_field_transform,')
    path.write_text(text,encoding='utf8',newline='')


if __name__=='__main__':main()
