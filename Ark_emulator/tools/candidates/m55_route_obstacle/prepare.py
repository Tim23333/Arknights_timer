"""Generic selected-route obstacle contact; finite cost does not imply a wall."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m52_visibility_stock_integrated_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m55_route_obstacle_candidate'


def edit(name,old,new):
    p=OUT/'ark_sim'/name;s=p.read_text(encoding='utf8')
    if old not in s:raise ValueError('Obstacle patch context drift: '+name)
    p.write_text(s.replace(old,new,1),encoding='utf8',newline='')


def main():
    if OUT.exists():raise ValueError('Candidate path already exists')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    edit('content/schemas.py','    "deployable": {','    "route_obstacle": {"rule", "contact_radius", "parameters"},\n    "deployable": {')
    edit('content/schemas.py','        advanced = components.get("deployable", {}).get("parameters", {}).get("advanced_build_mask")',
'''        obstacle=components.get("route_obstacle")
        if obstacle is not None:
            if set(obstacle)!={"rule","contact_radius","parameters"} or not isinstance(obstacle["rule"],str) or not obstacle["rule"] or not isinstance(obstacle["parameters"],Mapping):raise ContentError(identifier+": route obstacle requires rule, radius and explicit parameters")
            number(obstacle["contact_radius"],identifier+".route_obstacle.contact_radius",0)
        advanced = components.get("deployable", {}).get("parameters", {}).get("advanced_build_mask")''')
    edit('content/capabilities.py','    requirements = []','''    requirements = []
    for ident,definition in definitions.items():
        spec=definition.get("components",{}).get("route_obstacle")
        if spec is not None:
            rule=rules.get(spec["rule"])
            if rule is None or rule.get("contract")!="blocking.obstacle":raise ContentError(ident+": obstacle rule must implement blocking.obstacle")
            requirements.append({"calculation":"blocking.obstacle","rule":spec["rule"],"required_by":ident+".route_obstacle"})''')
    edit('domains/movement.py','        used = {ref: 0 for ref, _ in blockers}',
'''        obstacles=[e for e in entities if e["components"].get("route_obstacle") and e["components"].get("spatial",{}).get("position") is not None and not self.ctx.route_hidden(e["id"])]
        used = {ref: 0 for ref, _ in blockers}''')
    edit('domains/movement.py','            if current != self.blocked_by(ref):\n',
'''            if current is None:
                remaining=list(spatial.get("movement_path",()))
                cursor=spatial.get("movement",{}).get("path_index",0)
                if type(cursor) is not int or cursor<0:raise ValueError("route obstacle path index invalid")
                remaining=remaining[cursor:]
                for obstacle in sorted(obstacles,key=lambda e:(e["id"]!=previous,e["id"])):
                    spec=obstacle["components"]["route_obstacle"];other=obstacle["components"]["spatial"]["position"]
                    cell=project_cell(other)
                    if not any(project_cell(p)==cell for p in remaining) and project_cell(position)!=cell:continue
                    distance=math.hypot(other["row"]-position["row"],other["col"]-position["col"])
                    if distance>spec["contact_radius"]:continue
                    accepted=self.ctx.calc("blocking.obstacle",{"source":entity,"obstacle":obstacle,"path":remaining,
                        "distance":distance,"parameters":thaw(spec["parameters"])},source=ref,target=obstacle["id"],owner=obstacle["id"],rule_id=spec["rule"])
                    if type(accepted) is not bool:raise ValueError("blocking.obstacle must return strict boolean")
                    if accepted:
                        current=obstacle["id"];break
            if current != self.blocked_by(ref):
''')
    p=OUT/'ark_sim/rules/contracts.json';d=json.loads(p.read_bytes());d['contracts'].append({'id':'blocking.obstacle','kind':'calculation','owner':'source',
        'inputs':[{'name':n,'type':t,'required':True} for n,t in [('source','entity_snapshot'),('obstacle','entity_snapshot'),('path','path_plan'),('distance','number'),('parameters','value_map')]],
        'outputType':'boolean','implementations':['expression','graph','provider'],'pureEvaluation':True,'writesStateDirectly':False,'versionsRequired':True,
        'outputSchema':{'type':'boolean'},'contractVersion':1,'status':'declared','description':'Opt-in contact with an active obstacle on the selected remaining ground route; source policy decides eligibility.'});p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    rows={str(p.relative_to(OUT/'ark_sim')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'ark_sim').rglob('*.py'))};fp=hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();print(json.dumps({'core':fp,'candidate':str(OUT)}))


if __name__=='__main__':main()
