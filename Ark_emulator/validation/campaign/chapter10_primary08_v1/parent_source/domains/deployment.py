"""Shared deployment decisions for player cards and authored owned spawns."""
from ark_sim.contracts import thaw


def cooldown_start(deployable):
    start=deployable.get('cooldown_start','retire')
    if type(start) is not str or start not in ('deploy','retire'):
        raise ValueError('cooldown_start must be deploy or retire')
    return start


def prepare(context, definition_id, position, facing="right", owner=None, paid=False):
    definition = context.program.definitions.get(definition_id)
    if definition is None or definition.get("kind") != "entity":
        raise ValueError("unknown entity definition")
    if not isinstance(position, dict) or set(position) != {"row", "col"} or any(
            type(position[k]) is not int for k in ("row", "col")):
        raise ValueError("deployment requires integer cell coordinates")
    if facing not in {"right", "left", "up", "down"}:
        raise ValueError("deployment requires a declared facing")
    components = thaw(definition.get("components", {}))
    deployable = components.get("deployable", {})
    cooldown_start(deployable)
    prototype = {"definition_id": definition_id, "components": components, "tags": list(definition.get("tags", ()))}
    scope = {"source": definition.get("rules", {})}
    actors = [thaw(e) for e in context.session.world.entities()
              if context.active(e["id"]) and e["components"].get("deployable")]
    state = context.state()
    key = definition_id if owner is None else f"{definition_id}|owner:{owner}"
    history = state["deployments"].get(key, {"count": 0, "ready_at": 0})
    base = components.get("attributes", {}).get("base", {})
    roles = context.program.ruleset.get("parameters", {}).get("attribute_roles", {})
    cost = context.calc("deploy.cost", {
        "base_cost": deployable.get("base_cost", deployable.get("cost", base.get(roles.get("deploy_cost"), 0))),
        "deployment_history": history, "modifiers": []}, component=deployable.get("rules", {}),
        scope_extra=scope, extra={"source": prototype})
    resource = context.program.ruleset.get("parameters", {}).get("deployment_resource")
    capacity = context.calc("deploy.capacity", {"units": [e["id"] for e in actors],
        "capacity_parameters": {"capacity": context.program.scenario.get("parameters", {}).get("deploy_capacity", 100)}})
    used = sum(e["components"]["deployable"].get("capacity", 1) for e in actors)
    inside = context.spatial.grid.inside(position["row"], position["col"])
    tile = context.spatial.grid.tile(position["row"], position["col"]) if inside else {}
    same = [e for e in actors if e["definition_id"] == definition_id and (
        owner is None or e["components"].get("ownership", {}).get("owner") == owner)]
    token_occupied = False
    if inside and getattr(context,"tile_targets_enabled",False):
        from .tile_targets import blocks_deployment
        token_occupied = blocks_deployment(context, position)
    decision = context.calc("deploy.eligibility", {
        "entity": prototype, "location": position,
        "terrain": {**tile, "inside": inside, "buildable": tile.get("buildableType", 0),
                    "occupied": token_occupied or any(e["components"].get("spatial", {}).get("position") == position for e in actors)},
        "resources": {"affordable": paid or not resource or context.resources.current("system/battle", resource) >= cost},
        "states": {"finished": state["finished"], "instances": len(same),
                   "cooldown": context.session.time < history.get("ready_at", 0),
                   "at_capacity": used+deployable.get("capacity", 1) > capacity}},
        component=deployable.get("rules", {}), scope_extra=scope, extra={"source": prototype})
    if not decision["accepted"]:
        raise ValueError(decision["reason"])
    from .deploy_connectivity import inspect as inspect_connectivity
    inspect_connectivity(context,definition,position,deployable)
    stock=deployable.get("stock")
    stock_payment=None
    if stock is not None:
        amount=context.calc("resource.cost",{"ability":{},"attributes":base,"cost_parameters":{"amount":stock["amount"]}},
            component=deployable.get("rules",{}),scope_extra=scope,rule_id=stock.get("rule"),extra={"source":prototype})
        if type(amount) is not int or amount<0:raise ValueError("deployment stock cost must be a nonnegative integer")
        shared_cost=cost if not paid and stock["resource"]==resource else 0
        if context.resources.current("system/battle",stock["resource"])<amount+shared_cost:raise ValueError("insufficient deployment stock")
        stock_payment={"resource":stock["resource"],"amount":amount}
    return {"definition": definition_id, "position": position, "facing": facing, "owner": owner,
            "deployable": deployable, "cost": cost, "resource": resource, "history_key": key, "history": history, "stock_payment":stock_payment}


def record(context, ref, plan, paid_cost=None):
    with context.session.atomic():
        return _record(context,ref,plan,paid_cost)


def _record(context, ref, plan, paid_cost=None):
    if context.get(ref,("runtime","deployment_recorded"),False):raise ValueError("deployment already recorded")
    start=cooldown_start(plan['deployable'])
    if start=='deploy' or 'connectivity' in plan['deployable']:
        context.set(ref,('runtime','deployment_recorded'),True)
    from .deploy_connectivity import inspect as inspect_connectivity
    inspect_connectivity(context,context.program.definitions[plan['definition']],context.get(ref,('spatial','position')),context.get(ref,('deployable',),{}),entity=context.entity(ref),phase='record')
    stock=plan.get("stock_payment")
    if stock is not None:
        if context.resources.current("system/battle",stock["resource"])<stock["amount"]:raise ValueError("insufficient deployment stock")
        actual=context.resources.adjust("system/battle",stock["resource"],-stock["amount"],source=ref)
        if actual!=-stock["amount"]:raise ValueError("deployment stock payment must be exact")
    deployable = thaw(plan["deployable"])
    deployable["paid_cost"] = plan["cost"] if paid_cost is None else paid_cost
    deployable.setdefault("parameters", {})["history_key"] = plan["history_key"]
    context.set(ref, ("deployable",), deployable)
    if start=='deploy':
        cooldown=deployable['cooldown_seconds'] if 'cooldown_seconds' in deployable else context.role_value(ref,'redeploy_time')
        seconds=context.calc('deploy.cooldown',{'attributes':context.attributes.values(ref),'reason':{'type':'deployed'},'cooldown_parameters':{'seconds':cooldown}},source=ref,component=deployable.get('rules',{}))
        if type(seconds) not in (int,float) or seconds<0:raise ValueError('deployment cooldown must be finite nonnegative seconds')
        ready=context.session.time+context.quantize(seconds)
        current=context.state()['deployments'].get(plan['history_key'],{'count':0,'ready_at':0})
        history=dict(current,count=current['count']+1,ready_at=ready)
    else:
        history = dict(plan["history"], count=plan["history"]["count"]+1)
    state = context.state()
    state["deployments"][plan["history_key"]] = history
    context.state_update(**state)
    context.set(ref,("runtime","deployment_recorded"),True)
