"""Generic finite battle-resource stock shared by public and owned deployment."""
from pathlib import Path
import shutil,json,hashlib

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m50_deploy_stock_candidate'


def edit(name,before,after):
    p=OUT/'ark_sim'/name;text=p.read_text(encoding='utf8')
    if before not in text:raise ValueError('Candidate patch context drift '+name)
    text=text.replace(before,after,1);p.write_text(text,encoding='utf8',newline='')


def main():
    if OUT.exists():raise ValueError('Do not overwrite a stock candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    edit('content/schemas.py','"deployable": {"policy",','"deployable": {"stock", "policy",')
    edit('content/schemas.py','        advanced = components.get("deployable", {}).get("parameters", {}).get("advanced_build_mask")',
'''        stock=components.get("deployable",{}).get("stock")
        if stock is not None:
            fields(stock,{"resource","amount","rule"},identifier+".deployable.stock")
            if not isinstance(stock.get("resource"),str) or not stock["resource"] or type(stock.get("amount")) is not int or stock["amount"]<=0:
                raise ContentError(identifier+": stock requires nonempty battle resource and positive integer amount")
            if "rule" in stock and (not isinstance(stock["rule"],str) or not stock["rule"]):raise ContentError(identifier+": stock rule must be nonempty ID")
        advanced = components.get("deployable", {}).get("parameters", {}).get("advanced_build_mask")''')
    edit('content/compiler.py','            check_freeze(resources, entity.get("components", {}).get("abilities", []), identifier)',
'''            stock=entity.get("components",{}).get("deployable",{}).get("stock")
            if stock is not None:
                if stock["resource"] not in (scenario or {}).get("resources",{}):raise CompileError(identifier+": deployment stock resource is absent")
                if stock.get("rule") and definitions[stock["rule"]].get("contract")!="resource.cost":raise CompileError(identifier+": stock rule must implement resource.cost")
            check_freeze(resources, entity.get("components", {}).get("abilities", []), identifier)''')
    edit('domains/deployment.py','    if not decision["accepted"]:\n        raise ValueError(decision["reason"])',
'''    if not decision["accepted"]:
        raise ValueError(decision["reason"])
    stock=deployable.get("stock")
    stock_payment=None
    if stock is not None:
        amount=context.calc("resource.cost",{"ability":{},"attributes":base,"cost_parameters":{"amount":stock["amount"]}},
            component=deployable.get("rules",{}),scope_extra=scope,rule_id=stock.get("rule"),extra={"source":prototype})
        if type(amount) is not int or amount<0:raise ValueError("deployment stock cost must be a nonnegative integer")
        shared_cost=cost if not paid and stock["resource"]==resource else 0
        if context.resources.current("system/battle",stock["resource"])<amount+shared_cost:raise ValueError("insufficient deployment stock")
        stock_payment={"resource":stock["resource"],"amount":amount}''')
    edit('domains/deployment.py','"deployable": deployable, "cost": cost, "resource": resource, "history_key": key, "history": history}',
         '"deployable": deployable, "cost": cost, "resource": resource, "history_key": key, "history": history, "stock_payment":stock_payment}')
    edit('domains/deployment.py','    deployable = thaw(plan["deployable"])',
'''    stock=plan.get("stock_payment")
    if stock is not None:
        if context.resources.current("system/battle",stock["resource"])<stock["amount"]:raise ValueError("insufficient deployment stock")
        actual=context.resources.adjust("system/battle",stock["resource"],-stock["amount"],source=ref)
        if actual!=-stock["amount"]:raise ValueError("deployment stock payment must be exact")
    deployable = thaw(plan["deployable"])''')
    # Retain a patch and a byte-level candidate construction identity.
    rows={str(p.relative_to(OUT/'ark_sim')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'ark_sim').rglob('*.py'))}
    core=hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    print(json.dumps({'candidate':str(OUT),'core':core}))


if __name__=='__main__':main()
