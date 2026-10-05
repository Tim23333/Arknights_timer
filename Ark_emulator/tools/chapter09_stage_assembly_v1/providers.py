"""Explicit registry of source consumers; identical names cannot conflict."""


def providers():
    from tools.chapter09_more_content.build_v1 import providers as ordinary
    from tools.chapter09_coupled_v2.build_v2 import providers as coupled
    from tools.chapter09_duspfr_v1.build import providers as fire
    from tools.chapter09_demolition_v2.build import providers as demolition
    from tools.chapter09_pillar_v1.bigforce import eligibility
    registry = {}
    for group in (ordinary(), coupled(), fire(), demolition()):
        for name, record in group.items():
            if name in registry and registry[name] != record:
                raise ValueError('Conflicting provider identity: ' + name)
            registry[name] = record
    registry['reference.ch9.bigforce_cell'] = {'callable': eligibility, 'version': '1'}
    return registry
