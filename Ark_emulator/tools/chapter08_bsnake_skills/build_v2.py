"""Pin fixed56 x-5 rather than historical offline copy; preserve draft v1."""
import json
from pathlib import Path
from tools.chapter08_bsnake_skills.build_v1 import BASE,ROOT,sha
def main():
    old=BASE/'skills.module.v1.json';p=json.loads(old.read_bytes())
    source=BASE/'range.source.v1.json';fixed=ROOT.parent/'unpack_work/campaign_tables/range_table.json'
    assert sha(fixed)=='a98344d688a8933c4dd7ddaae3cb76c4347295359a18b60b918042cc2542d9d9'
    native=json.loads(fixed.read_bytes())['x-5'];assert native==json.loads(source.read_bytes())['selected_x5']
    offsets=[[v['row'],v['col']] for v in native['grids'] if (v['row'],v['col'])!=(0,0)]
    assert offsets==next(r for r in p['rules'] if r['contract']=='area.members')['parameters']['offsets']
    m=p['manifest']['metadata'];m['source_locks'].update({str(x):sha(x) for x in (fixed,source,old,Path(__file__))})
    m['range_source']=json.loads(source.read_bytes());m['reference_policies'][2]='BSON null rangeId/useRadius false consumes inline BB range_id x-5 with exact fixed56 table. Runtime project_cell geometry and node method body remain reference.'
    p['manifest']['id']='package/ch8/bsnake/skills_v2'
    out=BASE/'skills.module.v2.json';assert not out.exists();out.write_bytes((json.dumps(p,ensure_ascii=False,indent=2)+'\n').encode());print(sha(out))
if __name__=='__main__':main()
