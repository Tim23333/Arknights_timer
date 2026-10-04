"""Reuse frozen author guard wrapper with new focused scope/output only."""
from pathlib import Path
text=Path(__file__).with_name('verify_author_v3.py').read_text().replace('test_author_v3.py','test_boundaries_v1.py').replace('author.v3.tests.json','boundaries.v1.tests.json')
exec(compile(text,str(Path(__file__)),'exec'))
