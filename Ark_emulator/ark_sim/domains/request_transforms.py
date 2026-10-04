"""Pure request transform; unchanged fields retain their exact JSON values."""
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
