"""Explicit source registry for chapter8 native composition draft."""
def providers():
    from tools.chapter08_boss.talula_skill_policies_v3 import providers as boss
    from tools.chapter08_special.policies_v2 import providers as special
    from tools.chapter08_ranged.policies_v1 import providers as ranged
    from tools.chapter08_environment.policies_v1 import providers as infection
    return {**boss(),**special(),**ranged(),**infection()}
