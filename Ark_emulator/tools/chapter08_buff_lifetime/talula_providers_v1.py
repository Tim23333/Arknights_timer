def providers():
    from tools.chapter08_boss.talula_skill_policies_v3 import providers as talula
    from tools.chapter08_buff_lifetime.policies_v1 import providers as clocks
    return {**talula(),**clocks()}
