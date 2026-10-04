"""Explicit source dormant branch scope; no unbound branch silently discarded."""
from copy import deepcopy


def compose(native,native_id,bindings,tile_profiles,*,inactive_profile):
    from tools.chapter06_review.stage_converter_v7 import compose as previous,exact
    if (not isinstance(inactive_profile,dict) or set(inactive_profile)!={'native_branches','reason','source_consumer_documents'}
        or not exact(inactive_profile['native_branches'],native.get('branches'))
        or not inactive_profile['reason'] or not inactive_profile['source_consumer_documents']):
        raise ValueError('Exactsource branch profile and source consumer evidence required')
    keys=set(native['branches'])
    if not keys:raise ValueError('Inactivebranch profile requires actual branches')
    for wave in native['waves']:
        for fragment in wave['fragments']:
            for action in fragment['actions']:
                if action['key'] in keys or 'BRANCH' in action['actionType']:
                    raise ValueError('Source timeline may trigger declaredinactive branch')
    # Caller supplies full chosenconsumer documents. Reject any runtime branch
    # advance or source raw BB reference to branch keys in their actual source.
    def check(value):
        if isinstance(value,dict):
            if value.get('op')=='advance_branch':raise ValueError('Active branch consumer cannot be declaredinactive')
            if value.get('valueStr') in keys:raise ValueError('Source branch BB trigger remains active')
            for key,item in value.items():
                if key!='native_branches':check(item)
        elif isinstance(value,list):
            for item in value:check(item)
    for doc in inactive_profile['source_consumer_documents']:check(doc)
    view=deepcopy(native);view['branches']={}
    hard=native.get('hardPredefines')
    if hard:
        if (not isinstance(hard,dict) or set(hard)!={'characterInsts','tokenInsts','characterCards','tokenCards'}
            or any(v not in (None,{},[]) for v in hard.values())):
            raise ValueError('Nonemptyhardpredefines require explicit difficulty profile')
        view['hardPredefines']=None
    scene,controls=previous(view,native_id,bindings,tile_profiles)
    scene.setdefault('metadata',{})['inactive_source_branches']={
        'native_branches':deepcopy(native['branches']),'reason':inactive_profile['reason'],
        'runtime_branch_requests':False,'policy':'Source branch assets retained; selectedactors and source timeline do not trigger branch. Later consumer activation requires newprofile/conversion, never auto-ignore.'}
    scene['metadata']['empty_hard_predefines']={'native':deepcopy(hard),'selected_normal_difficulty':1,'all_buckets_verified_empty':True}
    return scene,controls
