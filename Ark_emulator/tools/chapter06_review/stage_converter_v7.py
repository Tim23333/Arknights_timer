"""Type-exact recursive source bindings before strict v6 stage conversion."""
from collections.abc import Mapping
from tools.chapter06_review.stage_converter_v6 import compose as previous


def exact(left,right):
    if type(left) is not type(right):return False
    if isinstance(left,Mapping):return set(left)==set(right) and all(exact(left[k],right[k]) for k in left)
    if isinstance(left,(list,tuple)):return len(left)==len(right) and all(exact(a,b) for a,b in zip(left,right))
    return left==right


def compose(native,native_id,bindings,tile_profiles,seed=None,story_controls=None,
            predefined_profile=None,*,story_key_profile=None,action_lifecycle_profiles=None):
    if predefined_profile is not None:
        if not exact(predefined_profile.get('native_predefines'),native['predefines']):
            raise ValueError('Predefine raw source identity must match recursively including types')
        for bucket in ('characterInsts','tokenInsts'):
            original=native['predefines'].get(bucket) or []
            converted=[r for r in predefined_profile.get('initial_entities',[]) if r.get('parameters',{}).get('native_bucket')==bucket]
            if len(original)!=len(converted) or any(not exact(r,c.get('parameters',{}).get('native_instance')) for r,c in zip(original,converted)):
                raise ValueError('Instance raw source identity must match recursively including types')
        for bucket in ('characterCards','tokenCards'):
            original=native['predefines'].get(bucket) or []
            converted=[r for r in predefined_profile.get('card_bindings',[]) if r.get('native_bucket')==bucket]
            if len(original)!=len(converted) or any(not exact(r,c.get('native_card')) for r,c in zip(original,converted)):
                raise ValueError('Card raw source identity must match recursively including types')
    for profile in action_lifecycle_profiles or []:
        if not isinstance(profile,dict):raise ValueError('Lifecycle profile requires mapping')
        try:
            indices=[profile[k] for k in ('wave','fragment','action')]
            if any(type(x) is not int or x<0 for x in indices):raise ValueError('Strict source action location')
            wi,fi,ai=indices;action=native['waves'][wi]['fragments'][fi]['actions'][ai]
        except (KeyError,IndexError,TypeError) as error:raise ValueError('Invalid source action location') from error
        if not exact(profile.get('native_action'),action):
            raise ValueError('Lifecycle action source identity must match recursively including types')
    return previous(native,native_id,bindings,tile_profiles,seed,story_controls,predefined_profile,
        story_key_profile=story_key_profile,action_lifecycle_profiles=action_lifecycle_profiles)
