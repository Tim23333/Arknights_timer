"""Version new audit helpers for distinct actual graph and provider callback wrappers."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DIR=ROOT/'tools/trace_audit'
def write(name,text):
 p=DIR/name;assert not p.exists();p.write_text(text,encoding='utf8',newline='')
def main():
 math=(DIR/'stream_oracle_v1.py').read_text()
 old="        for field,actual in [('nested.raw',child['raw']),('nested.value',child['value']),('graph.node.raw',node['raw']),('graph.node.value',node['value'])]:"
 new="""        fields=[('nested.raw',child['raw']),('nested.value',child['value'])]
        if node.get('kind')=='calculation':
         if node.get('id')!='calculation:'+child['calculation_id'] or node.get('calculation_id')!=child['calculation_id'] or node.get('rule_id')!=rid or set(node)!={'id','kind','calculation_id','rule_id','value','trace'}:raise Pending('nested.callback wrapper shape/identity not reviewed')
         fields.append(('callback.value',node['value']))
        elif 'kind' not in node and set(node)=={'id','raw','value','trace'}:
         fields.extend([('graph.node.raw',node['raw']),('graph.node.value',node['value'])])
        else:raise Pending('nested.wrapper typed shape not reviewed')
        for field,actual in fields:"""
 assert math.count(old)==1;math=math.replace(old,new);write('stream_oracle_v4_math.py',math)
 identity=(DIR/'stream_oracle_v2.py').read_text().replace('stream_oracle_v1 as base','stream_oracle_v4_math as base')
 old="    if node is not None:require('node.raw',want,node.get('raw'));require('node.value',want,node.get('value'))"
 new="""    if node is not None:
     if node.get('kind')=='calculation':
      require('callback.fields',['calculation_id','id','kind','rule_id','trace','value'],sorted(node))
      require('callback.id','calculation:'+t['calculation_id'],node.get('id'));require('callback.calculation_id',t['calculation_id'],node.get('calculation_id'));require('callback.rule_id',rid,node.get('rule_id'));require('callback.value',want,node.get('value'))
     elif 'kind' not in node:
      require('graph.fields',['id','raw','trace','value'],sorted(node));require('node.raw',want,node.get('raw'));require('node.value',want,node.get('value'))
     else:pending[prefix+'wrapper kind not source-reviewed']+=1;valid=False"""
 assert identity.count(old)==1;identity=identity.replace(old,new);write('stream_oracle_v4_identity.py',identity)
 public=(DIR/'stream_oracle_v3.py').read_text().replace('from tools.trace_audit.stream_oracle_v2 import audit as parent_audit','from tools.trace_audit.stream_oracle_v4_identity import audit as parent_audit').replace('stream-audit/v3','stream-audit/v4')
 public=public.replace('V3 adds standard graph call-context/binding inheritance, leaving V1/V2 frozen.','V4 uses source-typed callback/graph wrappers; all old audit versions remain frozen.')
 write('stream_oracle_v4.py',public)
 print('Wrote three new V4 helpers; no frozen source files modified')
if __name__=='__main__':main()
