"""Pure infection contact admission and nonrefreshing source Buff installation."""
from ark_sim.domains.providers import BUILTIN_PROVIDERS
from ark_sim.domains.spatial import project_cell
def contact(inputs,params,context):
 s=inputs['source']['components']['spatial']['position'];t=inputs['candidate']['components']['spatial']['position'];state=inputs['selection_states']['candidate']
 return {'accepted':project_cell(s)==project_cell(t) and bool(state['motion']&1) and bool(state['category']&1),'reason':'current_ground_character_contact_all_sides_sourceignoreflags'}
def infection_once(inputs,params,context):
 now=context['time'];buff=params['buff']
 live=any(i['definition']==buff and (i['expires_at'] is None or now<i['expires_at']) for i in inputs['instances'])
 return {'accepted':True,'operations':[] if live else [{'kind':'apply','buff':buff,'duration_seconds':params['duration'],'stacks':1}]}
def providers():return {**BUILTIN_PROVIDERS,'reference.c8.infection_contact':{'callable':contact,'version':'1'},'reference.c8.infection_once':{'callable':infection_once,'version':'1'}}
