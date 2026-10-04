"""Same source providers plus quantized start-relative skill cooldown."""


def recovery(inputs, params, context):
    q=context['quantum']
    speed=params['mapping_speed']*max(inputs['attributes']['attack_speed_ratio'],.01)
    quantized_duration=context.calculate('time.quantize',{'seconds':params['source_duration']/speed,'quantum':q,'rounding':{'mode':'ceil'}}).value
    quantized_delay=context.calculate('time.quantize',{'seconds':params['source_delay']/speed,'quantum':q,'rounding':{'mode':'ceil'}}).value
    duration=max(quantized_duration,quantized_delay)
    cooldown=context.calculate('time.quantize',{'seconds':inputs['recovery_parameters']['seconds'],'quantum':q,'rounding':{'mode':'ceil'}}).value
    return max(0,cooldown-duration)*q


def providers():
    from tools.chapter08_boss.talula_skill_policies_v1 import providers as previous
    return {**previous(),'reference.c8.talula.start_cooldown':{'callable':recovery,'version':'1'}}
