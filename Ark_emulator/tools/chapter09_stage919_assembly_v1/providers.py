"""Exact-source registry for the finale; no runtime fallback or registry override."""


def providers():
    from tools.chapter09_stage_assembly_v1.providers_v6 import providers as ordinary
    from tools.chapter09_receiver_hooks_v1.build import providers as receiver
    from tools.chapter09_mandra_v1.build import providers as mandra
    from tools.chapter08_environment.policies_v1 import providers as infection
    registry={}
    for group in (ordinary(),receiver(),mandra(),infection()):
        for name,record in group.items():
            if name in registry and registry[name]!=record:
                raise ValueError('Conflicting source provider: '+name)
            registry[name]=record
    return registry
