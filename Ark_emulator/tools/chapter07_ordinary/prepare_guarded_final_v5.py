"""New output fixtures for actual guarded author run; module v4 source stays frozen."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DIR=ROOT/'tools/chapter07_ordinary'
s=(DIR/'test_sotihd_final_v4.py').read_text().replace('chapter07_ordinary_final_v4','chapter07_ordinary_guarded_final_v5');out=DIR/'test_sotihd_guarded_final_v5.py';assert not out.exists();out.write_text(s,encoding='utf8',newline='')
s=(DIR/'test_sotihd_public_final_v4.py').read_text().replace('test_sotihd_final_v4','test_sotihd_guarded_final_v5').replace('chapter07_ordinary_public_final_v4','chapter07_ordinary_public_guarded_v5');out=DIR/'test_sotihd_public_guarded_v5.py';assert not out.exists();out.write_text(s,encoding='utf8',newline='');print('New output only; no behavioral assertion/module/core edits')
