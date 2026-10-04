"""Controlled hook correctly treats entirely absent parameters as defaultunhurtable rejection."""
from pathlib import Path
HERE=Path(__file__).parent
s=(HERE/'review_flame_v2.py').read_text().replace('flame_independent_v2','flame_independent_v3').replace("('consider_unhurtable' in inputs.effect.parameters", "('parameters' in inputs.effect and 'consider_unhurtable' in inputs.effect.parameters")
(HERE/'review_flame_v3.py').write_text(s,encoding='utf-8',newline='')
