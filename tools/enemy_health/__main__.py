"""python -m tools.enemy_health 入口"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from tools.enemy_health.main import main

main()
