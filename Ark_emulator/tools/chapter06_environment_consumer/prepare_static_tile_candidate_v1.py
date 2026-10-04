"""Opt-in generic source-bound static tile masks; independent candidate only."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PARENT=ROOT.parent/'unpack_work/campaign_chapter06_complete_base_v5_candidate';OUT=ROOT.parent/'unpack_work/campaign_declared_static_tile_v1_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not OUT.exists();OUT.mkdir();shutil.copytree(PARENT/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 p=OUT/'ark_sim/domains/tile_mechanics.py';s=p.read_text();needle='        if isinstance(p,Mapping) and p.get(\'type\')==\'periodic_effect_field\':';new="""        if isinstance(p,Mapping) and p.get('type')=='declared_static_tile':
            if set(p)!={'type','expected_options','expected_blackboard','expected_effects'}:raise ValueError('declared static tile requires exact source options/blackboard/effects')
            options=p['expected_options']
            if not isinstance(options,Mapping) or set(options)!={'buildableType','passableMask','heightType'}:raise ValueError('static tile options require explicit build/pass/height')
            from .terrain import validate_values
            validate_values(options)
            if p['expected_blackboard'] not in (None,{},[]) or p['expected_effects'] not in (None,{},[]):raise ValueError('static tile cannot consume nonempty blackboard/effects')
            continue
""";assert s.count(needle)==1;p.write_text(s.replace(needle,new+needle),encoding='utf8',newline='')
 p=OUT/'ark_sim/content/spatial_validation.py';s=p.read_text();needle='        for field in ("passableMask", "buildableType"):';new="""        static=profiles.get(key,{})
        if static.get('type')=='declared_static_tile':
            for field,expected in static['expected_options'].items():
                actual=tile.get(field)
                if type(actual) is not type(expected) or actual!=expected:fail(location+'.'+field,'static tile source option differs')
            for field,expected in [('blackboard',static['expected_blackboard']),('effects',static['expected_effects'])]:
                actual=tile.get(field)
                if type(actual) is not type(expected) or actual!=expected:fail(location+'.'+field,'static tile source data differs')
""";assert s.count(needle)==1;p.write_text(s.replace(needle,new+needle),encoding='utf8',newline='')
 p=OUT/'ark_sim/domains/spatial.py';s=p.read_text();needle='        for tile in self._tiles:\n';new="""        from .tile_mechanics import validate_profiles
        validate_profiles(self.tile_mechanics)
        for tile in self._tiles:
            profile=self.tile_mechanics.get(tile.get('tileKey'),{})
            if profile.get('type')=='declared_static_tile':
                for field,expected in profile['expected_options'].items():
                    if type(tile.get(field)) is not type(expected) or tile.get(field)!=expected:raise ValueError('static tile runtime source option differs')
                for field in ('blackboard','effects'):
                    expected=profile['expected_'+field]
                    if type(tile.get(field)) is not type(expected) or tile.get(field)!=expected:raise ValueError('static tile runtime source data differs')
""";assert s.count(needle)==1;p.write_text(s.replace(needle,new),encoding='utf8',newline='')
 changed=[str(p.relative_to(OUT)) for p in (OUT/'ark_sim').rglob('*.py') if sha(p)!=sha(PARENT/p.relative_to(OUT))];report={'parent':'a7059989b9db7f4bc0de954b32cb5c5ba10e6b92ce040c57ea0a193549b9709a','changed_files':changed,'semantics':'Only explicit source static build/pass/height/emptyBB/effects validation; actual Grid ground/fly/build APIs consume declared masks. No native tile-name special case and no automatic portal inference.','primary_or_live_modified':False};dest=ROOT/'validation/campaign/chapter06_environment_candidate_v1/prepared.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='');print(json.dumps(report))
if __name__=='__main__':main()
