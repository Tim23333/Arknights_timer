"""Pure declared grid membership plus separately bound target eligibility."""
from collections.abc import Mapping
from ark_sim.contracts import thaw
from .selection import validate_eligibility,validate_state
from .spatial import project_cell

def validate_parameters(options):
    if not isinstance(options,Mapping) or not {'offsets','eligibility'} <= set(options) or set(options)-{'offsets','eligibility','include_primary'}:raise ValueError('qualified area requires explicit offsets and eligibility')
    if 'include_primary' in options and type(options['include_primary']) is not bool:raise ValueError('qualified area include_primary requires explicit bool')
    offsets=options['offsets']
    if not isinstance(offsets,(list,tuple)) or not offsets or any(not isinstance(p,(list,tuple)) or len(p)!=2 or any(type(v) is not int for v in p) for p in offsets):raise ValueError('qualified area offsets require integer pairs')
    validate_eligibility(options['eligibility'],'qualified area eligibility')

def qualified_cell_offsets(inputs,params,context):
    options={**thaw(params),**thaw(inputs['parameters'])};validate_parameters(options)
    projection=context.get('area_selection_states')
    if not isinstance(projection,Mapping) or set(projection)!={'source','candidates'}:raise ValueError('qualified area requires explicit pure selection projection')
    source=context.get('source')
    if not isinstance(source,Mapping) or type(source.get('id')) is not int:raise ValueError('qualified area requires source snapshot')
    validate_state(projection['source'],complete=True)
    primary=None
    if options.get('include_primary',False):
        target=context.get('target')
        if not isinstance(target,Mapping) or type(target.get('id')) is not int:raise ValueError('qualified area include_primary requires captured target snapshot')
        primary=target['id']
    row,col=project_cell(inputs['center_position']);cells={(row+dr,col+dc) for dr,dc in options['offsets']};result=[]
    for candidate in inputs['candidates']:
        # Membership is a union. The primary must already be a live/visible
        # domain candidate, then passes the same pure qualification as the grid.
        if candidate['id'] != primary and project_cell(candidate['components']['spatial']['position']) not in cells:continue
        key=str(candidate['id'])
        if key not in projection['candidates']:raise ValueError('qualified area missing candidate selection state')
        state=projection['candidates'][key];validate_state(state,complete=True)
        decision=context.calculate('targeting.eligibility',{'source':source,'candidate':candidate,
            'selector':{'healing':False},'parameters':options['eligibility']['parameters'],
            'selection_states':{'source':projection['source'],'candidate':state}},rule_id=options['eligibility']['rule']).value
        if not isinstance(decision,Mapping) or set(decision)!={'accepted','reason'} or type(decision['accepted']) is not bool or not isinstance(decision['reason'],str):raise ValueError('qualified area eligibility must return strict decision')
        if decision['accepted']:result.append(candidate['id'])
    return result

def projection(context,source,candidates,parameters):
    """World reads occur at the domain boundary; providers get only snapshots."""
    validate_parameters(parameters);defaults=parameters['eligibility']['parameters']['defaults']
    return {'source':context.spatial.selection_state(source,defaults),
        'candidates':{str(candidate['id']):context.spatial.selection_state(candidate['id'],defaults) for candidate in candidates}}
