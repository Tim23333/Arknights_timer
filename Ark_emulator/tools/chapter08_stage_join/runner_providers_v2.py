"""Current chapter8 source provider registry including dynamic lifetime."""
def providers():
    from tools.chapter08_stage_join.runner_providers_v1 import providers as prior
    from tools.chapter08_buff_lifetime.policies_v1 import providers as clocks
    return {**prior(),**clocks()}
