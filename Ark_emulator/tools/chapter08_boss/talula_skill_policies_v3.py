"""Composed source skill providers with corrected burn refresh/reset."""
def providers():
    from tools.chapter08_boss.talula_skill_policies_v2 import providers as skills
    from tools.chapter08_boss.dragon_fire_policies_v3 import providers as fire
    return {**skills(),**fire()}
