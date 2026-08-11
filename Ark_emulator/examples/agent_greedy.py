"""GreedyDefender demo: heuristic AI plays a level and prints the result.

Run: python examples/agent_greedy.py [level_id] [max_steps]
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_emulator.agent_env import AgentEnv
from ark_emulator.agents import GreedyDefender, play_episode


def main():
    level_id = sys.argv[1] if len(sys.argv) > 1 else "level_main_01-01"
    max_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
    env = AgentEnv(level_id, squad=[
        {"charId": "char_284_spot", "phase": 0, "level": 50},
        {"charId": "char_502_nblade", "phase": 0, "level": 50},
        {"charId": "char_123_fang", "phase": 0, "level": 50},
        {"charId": "char_149_scave", "phase": 0, "level": 50},
        {"charId": "char_150_snakek", "phase": 0, "level": 50},
        {"charId": "char_002_amiya", "phase": 0, "level": 50}])
    agent = GreedyDefender(
        vanguards=("char_502_nblade", "char_123_fang", "char_149_scave"),
        blockers=("char_150_snakek",),
        medic=None,
        early_blocker="char_284_spot")
    reward, result, tick = play_episode(env, agent, max_steps=max_steps)
    print(f"level={level_id} result={result} tick={tick} "
          f"reward={reward:.1f}")
    print(f"stats={env.info()['stats']}")


if __name__ == "__main__":
    main()
