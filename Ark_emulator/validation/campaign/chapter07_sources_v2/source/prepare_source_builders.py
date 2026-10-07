"""Create chapter7-only extractor versions; old scripts and sources untouched."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DIR=ROOT/'tools/chapter07';PLANPIN='e5a60611432f7413689af811a069fb33aac57123bd58190f51161f8a01129339'
def main():
 for file in ('build_enemy_sources.py','build_predefined_sources.py'):
  s=(ROOT/'tools/chapter06'/file).read_text().replace('chapter06','chapter07').replace('chapter6','chapter7').replace('d310c3f98408b2686be3f065ab6212e552451b7505ec083a62418db564941608',PLANPIN)
  if file=='build_enemy_sources.py':
   s=s.replace("if any(len(found)!=1 for found in paths.values()):raise ValueError('exact chapter7 prefab missing/ambiguous')","missing_prefabs={key:[str(p) for p in found] for key,found in paths.items() if len(found)!=1}")
   s=s.replace('        path=found[0];prefab=',"        if len(found)!=1:\n            prefabs[key]={'status':'exact_prefab_missing_or_ambiguous','candidate_paths':[str(p) for p in found],'runtime_consumed':False};animations[key]={'status':'source_missing'};continue\n        path=found[0];prefab=")
   s=s.replace("        v['prefab_source']", "        v['prefab_source']")
  else:
   s=s.replace("for bucket in ('characterInsts', 'tokenInsts')", "for bucket in ('characterInsts', 'tokenInsts', 'characterCards', 'tokenCards')")
  out=DIR/file;assert not out.exists();out.write_text(s,encoding='utf8',newline='')
 print('Created new Chapter7 enemy/predefined extractors')
if __name__=='__main__':main()
