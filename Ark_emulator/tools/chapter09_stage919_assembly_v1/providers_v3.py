"""Finale registry explicitly selects Mandragora V2 source providers."""


def providers():
    from tools.chapter09_stage_assembly_v1.providers_v6 import providers as ordinary
    from tools.chapter09_receiver_hooks_v1.build import providers as receiver
    from tools.chapter09_mandra_v2.build import providers as mandra_v2
    from tools.chapter08_environment.policies_v1 import providers as infection
    from tools.chapter09_stage919_assembly_v1.providers_v2 import blocker
    registry={}
    for group in (ordinary(),receiver(),mandra_v2(),infection()):
        for name,record in group.items():
            if name in registry and registry[name]!=record:raise ValueError('Conflicting explicitly selected source provider: '+name)
            registry[name]=record
    registry['reference.ch9.finale_blocker']={'callable':blocker,'version':'strict-input-obstacle-v1'}
    return registry
