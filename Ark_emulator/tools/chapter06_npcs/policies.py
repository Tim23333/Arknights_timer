"""Content-side pure exact Buff-instance cleanup; no fixed actor IDs."""
def remove_named_instance(inputs,params,context):
    name=params['definition']
    if inputs['allowed']!=[name]:raise ValueError('Exact named Buff cleanup closure required')
    ops=[{'kind':'remove','buff':name,'instance':b['id'],'generation':b['generation']}
         for b in inputs['instances'] if b['definition']==name]
    return {'accepted':True,'operations':ops}


def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,'reference.c6.npc_remove_named':{'callable':remove_named_instance,'version':'1.0.0'},
        'reference.c6.npc_maxhp_heal':{'callable':maxhp_heal,'version':'1.0.0'},
        'reference.c6.npc_hp_lock':{'callable':hp_lock,'version':'1.0.0'}}


def effective_maxhp(entity,context):
    data=entity['components']['attributes']
    modifiers=[m for m in data.get('modifiers',[]) if m['attribute']=='max_hp']
    return context.calculate('attributes.effective',{'base':data['base']['max_hp'],'modifier_layers':modifiers,
        'order':[{'layer':layer} for layer in data.get('layers',['flat','direct_ratio','final_ratio'])]}).value


def maxhp_heal(inputs,params,context):
    return effective_maxhp(context['source'],context)*params['ratio']


def hp_lock(inputs,params,context):
    from ark_sim.contracts import thaw
    value=thaw(inputs['effect']['settlement']);hp=inputs['target']['components']['resources']['hp']['current']
    value['amount']=min(value['amount'],max(0,hp-effective_maxhp(inputs['target'],context)*params['ratio']))
    return value
