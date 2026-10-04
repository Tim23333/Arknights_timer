"""Reproduce exact AB type trees using pinned offline decoder, no runtime edit."""
import ast,json,hashlib
from pathlib import Path
import UnityPy
from UnityPy.helpers import CompressionHelper
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'packages/campaign/chapter08_stage_controls/source'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class ProfilerOnly(ast.NodeTransformer):
    def visit_ImportFrom(self,node):
        if node.module=='utils.Profiler' and node.level==2:return None
        return node
    def visit_With(self,node):
        if len(node.items)==1 and isinstance(node.items[0].context_expr,ast.Call) and getattr(node.items[0].context_expr.func,'id',None)=='CodeProfiler':return node.body
        return self.generic_visit(node)
def main():
    raw=BASE/'config_common.fixed56.ab';source=BASE/'lz4ak.Block.pinned.py';expected=BASE/'config_common.decoded.json';before={str(p):sha(p) for p in (raw,source,expected)}
    tree=ast.fix_missing_locations(ProfilerOnly().visit(ast.parse(source.read_text())))
    scope={};exec(compile(tree,str(source),'exec'),scope);original=CompressionHelper.DECOMPRESSION_MAP[4]
    try:
        CompressionHelper.DECOMPRESSION_MAP[4]=scope['decompress_lz4ak'];env=UnityPy.load(raw.read_bytes());rows=[]
        for obj in env.objects:
            if obj.type.name=='MonoBehaviour':rows.append({'path_id':obj.path_id,'raw':obj.read_typetree()})
        actual={'container':list(env.container),'monos':rows};saved=json.loads(expected.read_bytes());assert sorted(actual['container'])==sorted(saved['container']);assert {str(v['path_id']):v['raw'] for v in rows}=={str(v['path_id']):v['raw'] for v in saved['monos']}
        asset=next(row for row in rows if row['raw']['m_Name']=='main_08-17');assert len(asset['raw']['_commands'])==2
    finally:CompressionHelper.DECOMPRESSION_MAP[4]=original
    assert {str(p):sha(p) for p in (raw,source,expected)}==before
    out=BASE/'opera.decode.reproduction.v2.json';assert not out.exists();out.write_text(json.dumps({'status':'exact_type_tree_reproduction_passed','source_before':before,'source_after':before,'helper_sha256':sha(Path(__file__)),'offline_only':True,'runtime_changed':False},indent=2)+'\n',encoding='utf8');print(sha(out))
if __name__=='__main__':main()
