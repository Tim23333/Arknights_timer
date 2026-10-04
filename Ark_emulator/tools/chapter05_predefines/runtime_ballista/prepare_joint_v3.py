"""Keep old146 source chain, clone only new combined-stage input path for8fa."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 old=ROOT/'tools/experiments/chapter05_complete_v1/test_source_chain.py';dest=Path(__file__).with_name('test_source_chain_v3.py')
 if dest.exists():raise ValueError('Preserve joint cases')
 text=old.read_text(encoding='utf8');oldpath='chapter05_stage_models/combined_v2/level_main_05-10.life99999.json';newpath='chapter05_stage_models/combined_v3/level_main_05-10.life99999.json';assert text.count(oldpath)+text.count(newpath)==1;text=text.replace(oldpath,newpath,1);dest.write_text(text,encoding='utf8',newline='');print({'original_sha':hashlib.sha256(old.read_bytes()).hexdigest(),'clone_sha':hashlib.sha256(dest.read_bytes()).hexdigest(),'behavior_assertions_changed':False})
if __name__=='__main__':main()
