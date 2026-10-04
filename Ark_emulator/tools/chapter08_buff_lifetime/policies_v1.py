"""Pure arbitrary lifetime-rate and source-resistant duration recipes."""
import math
def rate(inputs,params,context):
    multiplier=inputs['attributes'].get(params['attribute'],1)
    if type(multiplier) not in (int,float) or not math.isfinite(multiplier):raise ValueError('Lifetime multiplier finite numeric required')
    return 1/min(params['maximum'],max(params['minimum'],multiplier))
def providers():
    from ark_sim.domains.providers import BUILTIN_PROVIDERS
    return {**BUILTIN_PROVIDERS,'reference.c8.dynamic_buff_rate':{'callable':rate,'version':'1'}}
