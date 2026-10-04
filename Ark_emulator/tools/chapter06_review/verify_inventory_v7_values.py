"""Check actual combined definitions against fixed enemy and NPC source operands."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    package=ROOT/'validation/campaign/chapter06_join_inventory_v7/compile_input.json'
    enemies=ROOT/'packages/campaign/chapter06_sources/native.reference.json'
    npcs=ROOT/'packages/campaign/chapter06_npcs/inputs.reference.json'
    defs=json.loads(package.read_bytes())['definitions'];source=json.loads(enemies.read_bytes())['variants']
    rows=[]
    for d in defs:
        if d['kind']!='entity':continue
        vid=d.get('metadata',{}).get('native_variant_id')
        if vid:
            raw=source[vid]['native_enemy']['resolved']['attributes'];a=d['components']['attributes']['base']
            for dest,key in [('max_hp','maxHp'),('atk','atk'),('def','def'),('mres','magicResistance'),('move_speed','moveSpeed')]:
                assert type(a[dest]) is type(raw[key]) or type(a[dest]) in (int,float) and type(raw[key]) in (int,float)
                assert a[dest]==raw[key],(vid,dest)
            assert d['components']['resources']['hp']['initial']==raw['maxHp']
            rows.append({'variant':vid,'raw_hp':raw['maxHp'],'initial_hp':d['components']['resources']['hp']['initial'],'passed':True})
    assert len(rows)==7
    for native in json.loads(npcs.read_bytes())['records']:
        key=native['character_id'];unit=next(d for d in defs if d['kind']=='entity' and d.get('metadata',{}).get('native_character')==key)
        a=unit['components']['attributes']['base'];stats=native['stats']
        assert (a['max_hp'],a['atk'],a['def'])==(stats['maxHp'],stats['atk'],stats['def'])
        assert unit['components']['resources']['hp']['initial']==stats['maxHp'] and 'sp' not in unit['components']['resources']
        assert native['skill_index']==-1 and native['selected_skill'] is None
        rows.append({'npc':key,'hp':stats['maxHp'],'no_selected_skill_or_sp':True,'passed':True})
    trap=next(d for d in defs if d['id']=='unit/ch6/predefined/frosts/source_level1')
    assert trap['components']['attributes']['base']['max_hp']==trap['components']['resources']['hp']['initial']==100
    rows.append({'trap_hp':100,'passed':True})
    out=ROOT/'validation/campaign/chapter06_inventory_v7_values';out.mkdir(exist_ok=False)
    report={'passed':True,'cases':rows,'pins':{str(p):sha(p) for p in [package,enemies,npcs,Path(__file__)]},
        'scope':'Fixed source operands and HP/no-SP inputs in actual combined compile input. No source behavior/fullstage/numeric allfields/client claim'}
    target=out/'verification.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'passed':True,'cases':len(rows),'sha':sha(target)}))


if __name__=='__main__':main()
