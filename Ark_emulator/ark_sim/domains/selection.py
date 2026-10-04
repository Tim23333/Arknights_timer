"""Explicit model eligibility; native ValidateTarget bodies remain unverified."""
from collections.abc import Mapping
from ark_sim.contracts import thaw

BOOLS = {"target_free", "ally_target_free", "heal_free", "camouflage", "can_select_camouflage"}
MASKS = {"motion": 3, "category": 7, "profession": 1023, "unit_type": 7}
SETS = {"abnormal_flags": 46, "abnormal_combos": 2, "target_free_flags": 46, "target_free_combos": 2}
MANDATORY_FIELDS = BOOLS | set(MASKS) | set(SETS) | {"side"}
SETS["abnormal_immunes"] = 46
SETS["abnormal_combo_immunes"] = 2
FIELDS = MANDATORY_FIELDS | {"abnormal_immunes","abnormal_combo_immunes"}
DEFAULT_STATE = {**{x:False for x in BOOLS}, **{x:0 for x in MASKS}, **{x:[] for x in SETS if x!="abnormal_combo_immunes"}, "side":0}
SWITCHES = ("_ignoreTargetFree", "_onlyIgnoreSomeOfTargetFreeCase", "_excludeSomeAbnormalFlags", "_needProfessionMask", "_ignoreAllyTargetFree", "_ignoreHealFree", "_ignoreMotionMode", "_forceIgnoreCamouflage", "_checkUnitType")

def validate_state(state, path="selection_state", contribution=False, complete=False):
    if not isinstance(state, Mapping) or set(state)-FIELDS:
        raise ValueError(path+": unknown selection state fields")
    if complete and not MANDATORY_FIELDS <= set(state):
        raise ValueError(path+": explicit complete typed defaults required")
    if contribution and set(state)-(BOOLS | set(SETS)):
        raise ValueError(path+": Buff contributions may only union status flags")
    for k,v in state.items():
        if k in BOOLS and type(v) is not bool:
            raise ValueError(path+"."+k+": bool required")
        if k == "side" and (type(v) is not int or v not in (0,1,2)):
            raise ValueError(path+".side: absolute SideTypeIndex required")
        if k in MASKS and (type(v) is not int or v < 0 or v & ~MASKS[k]):
            raise ValueError(path+"."+k+": typed mask invalid")
        if k in SETS and (not isinstance(v,(list,tuple)) or any(type(x) is not int or not 0 <= x < SETS[k] for x in v) or len(set(v)) != len(v)):
            raise ValueError(path+"."+k+": known enum indices required; E_NUM is not a state")

def validate_eligibility(spec, path="eligibility"):
    if not isinstance(spec, Mapping) or (set(spec)-{"rule","parameters","include_candidate_tile"} or not {"rule","parameters"}<=set(spec)) or not isinstance(spec["rule"],str) or not spec["rule"]:
        raise ValueError(path+": exact rule and parameters required")
    if "include_candidate_tile" in spec and type(spec["include_candidate_tile"]) is not bool:raise ValueError(path+": include_candidate_tile requires strict boolean")
    p=spec["parameters"]
    if not isinstance(p,Mapping) or set(p) != {"source_configuration","side_policy","neutral_policy","defaults"}:
        raise ValueError(path+": explicit source_configuration/side_policy/neutral_policy/defaults required")
    if p["side_policy"] != "relative_ally_enemy" or p["neutral_policy"] not in {"reject", "absolute_mask"}:
        raise ValueError(path+": unsupported declared side/neutral model policy")
    validate_state(p["defaults"],path+".defaults",complete=True)
    c=p["source_configuration"]
    if not isinstance(c,Mapping): raise ValueError(path+": raw configuration record required")
    for k in SWITCHES:
        if k not in c or type(c[k]) not in (bool,int) or c[k] not in (0,1): raise ValueError(path+"."+k+": bool or serialized0/1 required")
    for k,mask,enabled in (("_targetSide",7,True),("_targetCategory",7,True),("_targetMotion",3,not c["_ignoreMotionMode"]),("_professionMask",1023,c["_needProfessionMask"]),("_unitTypeMask",7,c["_checkUnitType"])):
        if enabled and (type(c.get(k)) is not int or c[k]<0 or c[k]&~mask): raise ValueError(path+"."+k+": enabled typed mask invalid")
    if c["_ignoreTargetFree"] and c["_onlyIgnoreSomeOfTargetFreeCase"]:
        for k,bound in (("_abnormalFlag",46),("_abnormalCombo",2)):
            if type(c.get(k)) is not int or not 0 <= c[k] < bound: raise ValueError(path+"."+k+": enabled enum must be known, not E_NUM")
    if c["_excludeSomeAbnormalFlags"] and (type(c.get("_excludeAbnormalFlag")) is not int or not 0 <= c["_excludeAbnormalFlag"] < 46):
        raise ValueError(path+"._excludeAbnormalFlag: enabled known enum required")

def project_state(ctx, ref, defaults):
    validate_state(defaults, "projection.defaults", complete=True)
    result=thaw(defaults)
    combo_declared = "abnormal_combo_immunes" in defaults
    result.setdefault("abnormal_combo_immunes", [])
    immunity_declared = "abnormal_immunes" in defaults
    result.setdefault("abnormal_immunes", [])
    base=ctx.entity(ref)["components"].get("selection_state",{})
    validate_state(base)
    immunity_declared = immunity_declared or "abnormal_immunes" in base
    combo_declared = combo_declared or "abnormal_combo_immunes" in base
    result.update(thaw(base))
    for key in SETS: result[key]=set(result[key])
    now=ctx.session.time
    for instance in ctx.get(ref,("buffs","instances"),[]):
        if instance.get("expires_at") is not None and now >= instance["expires_at"]: continue
        if not instance.get("applicability",{}).get("active",True):continue
        flags=ctx.program.definitions[instance["definition"]].get("selection_flags",{})
        combo_declared = combo_declared or "abnormal_combo_immunes" in flags
        immunity_declared = immunity_declared or "abnormal_immunes" in flags
        for key,value in flags.items():
            if key in SETS: result[key].update(value)
            elif value: result[key]=True
    for key in SETS: result[key]=sorted(result[key])
    result["abnormal_flags"] = sorted(set(result["abnormal_flags"]) - set(result["abnormal_immunes"]))
    result["abnormal_combos"] = sorted(set(result["abnormal_combos"])-set(result["abnormal_combo_immunes"]))
    if not combo_declared:result.pop("abnormal_combo_immunes",None)
    # Only explicit native named status indices become corresponding flags.
    flags=result["abnormal_flags"]
    for name,index in (("target_free",2),("ally_target_free",15),("heal_free",7),("camouflage",17)):
        result[name]=result[name] or index in flags
    if not immunity_declared:result.pop("abnormal_immunes", None)
    return result

def eligibility_profile(inputs, params, context):
    p=inputs["parameters"];c=p["source_configuration"]
    s=inputs["selection_states"]["source"];t=inputs["selection_states"]["candidate"]
    def no(reason): return {"accepted":False,"reason":reason}
    side=c["_targetSide"]
    if s["side"]==2 or t["side"]==2:
        if p["neutral_policy"]=="reject": return no("neutral_policy")
        bit=1<<t["side"]
    else: bit=1 if s["side"]==t["side"] else 2
    if not side & bit: return no("side")
    if not c["_targetCategory"] & t["category"]: return no("category")
    if not c["_ignoreMotionMode"] and not c["_targetMotion"] & t["motion"]: return no("motion")
    if c["_needProfessionMask"] and not c["_professionMask"] & t["profession"]: return no("profession")
    if c["_checkUnitType"] and not c["_unitTypeMask"] & t["unit_type"]: return no("unit_type")
    if c["_excludeSomeAbnormalFlags"] and c["_excludeAbnormalFlag"] in t["abnormal_flags"]: return no("excluded_abnormal")
    if t["target_free"]:
        if not c["_ignoreTargetFree"]: return no("target_free")
        if c["_onlyIgnoreSomeOfTargetFreeCase"]:
            # Explicit reason-set model; unexplained aggregate free is not bypassed.
            flags=set(t["target_free_flags"]);combos=set(t["target_free_combos"])
            if not flags and not combos or flags-{c["_abnormalFlag"]} or combos-{c["_abnormalCombo"]}: return no("remaining_target_free_cause")
    if s["side"]==t["side"] and t["ally_target_free"] and not c["_ignoreAllyTargetFree"]: return no("ally_target_free")
    if inputs["selector"].get("healing") and t["heal_free"] and not c["_ignoreHealFree"]: return no("heal_free")
    if t["camouflage"] and not c["_forceIgnoreCamouflage"] and not s["can_select_camouflage"]: return no("camouflage")
    return {"accepted":True,"reason":"eligible_declared_profile"}
