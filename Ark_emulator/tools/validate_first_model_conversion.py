"""Validate the declared JSON-schema subset and actual draft/source identities."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def validate_schema(value,schema,pointer='$'):
    """Offline evaluator for the explicit schema vocabulary used by this draft."""
    from tools.build_first_model_conversion import require
    if 'const' in schema:require(type(value) is type(schema['const']) and value==schema['const'],pointer+': constant mismatch')
    if 'enum' in schema:require(value in schema['enum'],pointer+': enum mismatch')
    kind=schema.get('type')
    types={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool}
    if kind:require(type(value) is types[kind],pointer+': type mismatch')
    if kind=='object':
        require(all(k in value for k in schema.get('required',[])),pointer+': missing field')
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False:require(set(value)<=set(props),pointer+': unsupported field')
        for key,child in value.items():
            if key in props:validate_schema(child,props[key],pointer+'/'+key)
            elif isinstance(schema.get('additionalProperties'),dict):validate_schema(child,schema['additionalProperties'],pointer+'/'+key)
    elif kind=='array':
        require(len(value)>=schema.get('minItems',0),pointer+': too few items')
        require(len(value)<=schema.get('maxItems',len(value)),pointer+': too many items')
        if schema.get('uniqueItems'):require(len({json.dumps(x,sort_keys=True) for x in value})==len(value),pointer+': duplicate items')
        if 'items' in schema:
            for index,child in enumerate(value):validate_schema(child,schema['items'],pointer+'/'+str(index))
    elif kind=='string':require(len(value)>=schema.get('minLength',0),pointer+': empty string')


def validate():
    from tools.build_first_model_conversion import CONTENT,COMMAND_OUTPUT,AUDIT,SCHEMA,read,sha,require,build,CORE
    content=read(CONTENT);campaign=content['scenarioDraft']['metadata']['campaign']
    validate_schema(campaign,read(SCHEMA))
    expected,commands,audit=build()
    require(content==expected and read(COMMAND_OUTPUT)==commands and read(AUDIT)==audit,'source/output conversion mismatch')
    for source in campaign['source_locks']:
        require(sha(ROOT/source['path'])==source['sha256'],'source lock does not match actual bytes')
    require(campaign['pending_mechanics'] and campaign['native_fields_verified'] is False,'draft accidentally claims execution eligibility')
    require(campaign['implementation_sha256']==CORE,'implementation identity changed')
    return {'schema':'ark-sim/conversion-draft-validation/v1','passed':True,'implementation_sha256':CORE,
        'content_sha256':sha(CONTENT),'commands_sha256':sha(COMMAND_OUTPUT),'audit_sha256':sha(AUDIT),
        'field_count':len(audit['field_audit']),'status':'structurally_valid_draft_still_blocked','formal_approval':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=validate()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result))
