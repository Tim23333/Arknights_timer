"""Resolve compiler-generated scheduler names without accepting new layouts.

The compiler's numeric suffix changes when scheduler methods are inserted.
Names are version data; the iterator fields consumed by wave_state must still
match its validated topology before the bundle can be published.
"""
import re


METHODS = {'root': '_DoSchedule', 'wave': '_DealWave', 'fragment': '_DealFragment',
           'pre_delay': 'WaitForPredelay', 'post_delay': 'WaitForPostDelay',
           'actions': 'ExecuteActionQueue'}
CONTAINERS = {role: 'Scheduler' if role in ('root', 'wave', 'fragment')
              else 'Scheduler.DefaultWaveHandler' for role in METHODS}
COMMON_FIELDS = {'<>1__state': 0x10, '<>2__current': 0x18, '<>4__this': 0x20}
LAYOUTS = {
    'root': {**COMMON_FIELDS, '<>7__wrap1': 0x28, '<i>5__3': 0x40},
    'wave': {**COMMON_FIELDS, 'wave': 0x28, 'nextWave': 0x30, '<i>5__2': 0x38},
    'fragment': {**COMMON_FIELDS, 'fragment': 0x28},
    'pre_delay': {'<>1__state': 0x10, '<>2__current': 0x18, 'wave': 0x20},
    'post_delay': {'<>1__state': 0x10, '<>2__current': 0x18, 'wave': 0x20},
    'actions': {**COMMON_FIELDS, '<i>5__2': 0x28, '<item>5__3': 0x30},
}


def is_scheduler_coroutine(namespace: str, name: str) -> bool:
    return namespace == '' and any(
        re.fullmatch(rf'{re.escape(CONTAINERS[role])}\.<{method}>d__\d+', name)
        for role, method in METHODS.items()
    )


def scheduler_coroutines(classes: dict) -> dict[str, str]:
    result = {}
    for role, method in METHODS.items():
        candidates = [(name, fields) for (namespace, name), fields in classes.items()
                      if namespace == '' and re.fullmatch(
                          rf'{re.escape(CONTAINERS[role])}\.<{method}>d__\d+', name)]
        if len(candidates) != 1:
            raise ValueError(f'Expected one scheduler {role} iterator, found {len(candidates)}')
        name, fields = candidates[0]
        if any(fields.get(key) != offset for key, offset in LAYOUTS[role].items()):
            raise ValueError(f'Unsupported scheduler {role} iterator layout: {name}')
        result[role] = name.removeprefix(CONTAINERS[role] + '.')
    return result
