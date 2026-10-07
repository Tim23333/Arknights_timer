"""Original stage providers plus explicitly selected ally elemental receivers."""


def providers(stage):
    from tools.campaign_elemental_receivers_v1.build import providers as receivers
    if stage == '09-16':
        from tools.chapter09_stage_assembly_v1.providers_v6 import providers as original
    elif stage == '09-17':
        from tools.chapter09_stage919_assembly_v1.providers_v3 import providers as original
    else:
        raise ValueError('Selected exact source chapter9 stage required')
    registry = original()
    for name, record in receivers().items():
        if name in registry and registry[name] != record:
            raise ValueError('Conflicting source provider ' + name)
        registry[name] = record
    return registry
