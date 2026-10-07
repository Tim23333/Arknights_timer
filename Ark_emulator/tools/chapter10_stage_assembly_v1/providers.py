"""Explicitly bound source registries for chapter10 stage assembly."""


def providers():
    from tools.chapter10_remaining_v2.build import providers as lord
    from tools.chapter10_remaining_v1.build import providers as supply
    from tools.chapter10_dkmage_source_v1.build import providers as mage
    from tools.chapter10_gunctrl_v3.build import providers as cannon
    from tools.campaign_elemental_receivers_v1.build import providers as receiver
    registry = {}
    for group in (lord(), supply(), mage(), cannon(), receiver()):
        for name, value in group.items():
            if name in registry and registry[name] != value:
                raise ValueError('Conflicting source provider ' + name)
            registry[name] = value
    return registry
