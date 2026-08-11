"""AgentEnv demo: random-policy AI plays a level and prints a summary.

Run: python examples/agent_play.py [level_id] [steps]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.agent_env import AgentEnv, play_random


def main():
    level_id = sys.argv[1] if len(sys.argv) > 1 else "level_main_01-01"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    env = AgentEnv(level_id, squad=[
        {"charId": "char_149_scave", "phase": 2, "level": 50, "skillIndex": 0},
        {"charId": "char_002_amiya", "phase": 2, "level": 50, "skillIndex": 2},
    ])
    total, result, tick = play_random(env, steps=steps, seed=0)
    print(f"level={level_id} result={result} tick={tick} "
          f"reward={total:.1f} stats={env.info()['stats']}")


if __name__ == "__main__":
    main()
