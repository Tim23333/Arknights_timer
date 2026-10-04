"""Compose stage modules through the active compiler's dependency semantics.

No module imports/rebinds a runtime here. Callers select their candidate before
calling this helper. Equal duplicate definitions are allowed; conflicting
definitions require an explicit, complete replacement with provenance.
"""
from copy import deepcopy


def compose_modules(modules, replacements=None):
    from ark_sim.content.repository import Repository, load_sources
    from ark_sim.contracts.models import digest

    definitions, provenance = {}, {}
    for label, package in modules:
        repository = Repository(load_sources(package))
        for identifier, definition in repository.raw.items():
            if definition.get('kind') == 'scenario':
                continue
            if identifier in definitions and definitions[identifier] != definition:
                raise ValueError(f'Conflicting definition {identifier}: {provenance[identifier]} and {label}')
            definitions[identifier] = deepcopy(definition)
            provenance.setdefault(identifier, []).append({'module': label, 'definition_digest': digest(definition)})
    for identifier, replacement in (replacements or {}).items():
        if identifier not in definitions:
            raise ValueError(f'Replacement requires an existing definition: {identifier}')
        if set(replacement) != {'definition', 'reason', 'source'} or not replacement['reason'] or not replacement['source']:
            raise ValueError(f'Replacement requires reason and source: {identifier}')
        value = replacement['definition']
        if value.get('id') != identifier or value.get('kind') != definitions[identifier].get('kind'):
            raise ValueError(f'Replacement cannot change definition identity or kind: {identifier}')
        provenance[identifier].append({'replacement': deepcopy(replacement), 'definition_digest': digest(value)})
        definitions[identifier] = deepcopy(value)
    return definitions, provenance


def reachable_content(scene, modules, replacements=None, manifest_id='package/reference_stage', *, providers=None):
    """Return author definitions actually reached by a separately compiled scene.

    Preset definitions stay in the preset. Raw author definitions stay raw so
    inheritance and calculation references preserve normal compiler semantics.
    The report records retained and removed IDs, without asserting game fidelity.
    """
    from ark_sim import Compiler
    from ark_sim.contracts.models import thaw, digest

    definitions, provenance = compose_modules(modules, replacements)
    source = {'schemaVersion': 2, 'definitions': list(definitions.values())}
    program = Compiler(providers=providers).compile(scene, packages=source)
    reached = set(program.dependency_ids)
    retained = sorted(reached & set(definitions))
    removed = sorted(set(definitions) - reached)
    report = {'schema': 'ark-sim/reference-stage-composition/v1',
              'retained_ids': retained, 'removed_ids': removed,
              'definition_provenance': {key: provenance[key] for key in retained},
              'dependency_edges': thaw(program.metadata['dependency_edges']),
              'compiled_fingerprint': program.fingerprint,
              'scene_digest': digest(scene), 'actual_client_verified': False}
    result = {'schemaVersion': 2,
              'manifest': {'id': manifest_id, 'version': '1.0.0', 'requires': ['preset/ark_standard'],
                           'metadata': {'composition': report}},
              'definitions': [deepcopy(definitions[key]) for key in retained],
              'scenarioDraft': deepcopy(scene)}
    # A fresh compilation must retain precisely the same executable program.
    second = Compiler(providers=providers).compile(result)
    if set(second.dependency_ids) != reached:
        raise ValueError('Pruned package changed its executable dependency closure')
    if (thaw(second.definitions) != thaw(program.definitions)
            or thaw(second.scenario) != thaw(program.scenario)
            or thaw(second.ruleset) != thaw(program.ruleset)
            or thaw(second.rules) != thaw(program.rules)):
        raise ValueError('Pruned package changed executable definition values')
    return result, report
