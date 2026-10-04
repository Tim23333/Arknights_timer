"""Exact deployment payment and single-record World guard, independent branch."""
from pathlib import Path
import shutil,json,hashlib

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT.parent/'unpack_work/campaign_m50_deploy_stock_candidate'
OUT=ROOT.parent/'unpack_work/campaign_m51_deploy_payment_candidate'


def main():
    if OUT.exists():raise ValueError('Candidate already exists')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    p=OUT/'ark_sim/domains/deployment.py';s=p.read_text(encoding='utf8');old='def record(context, ref, plan, paid_cost=None):\n    stock=plan.get("stock_payment")';new='''def record(context, ref, plan, paid_cost=None):
    if context.get(ref,("runtime","deployment_recorded"),False):raise ValueError("deployment already recorded")
    stock=plan.get("stock_payment")''';assert old in s;s=s.replace(old,new,1)
    s=s.replace('    context.state_update(**state)\n','    context.state_update(**state)\n    context.set(ref,("runtime","deployment_recorded"),True)\n',1)
    s=s.replace('def record(context, ref, plan, paid_cost=None):\n','def record(context, ref, plan, paid_cost=None):\n    with context.session.atomic():\n        return _record(context,ref,plan,paid_cost)\n\n\ndef _record(context, ref, plan, paid_cost=None):\n',1)
    p.write_text(s,encoding='utf8',newline='')
    p=OUT/'ark_sim/adapters/api.py';s=p.read_text(encoding='utf8');old='''        if plan["resource"]:
            self.ctx.resources.adjust("system/battle", plan["resource"], -plan["cost"])''';new='''        if plan["resource"]:
            actual_paid=self.ctx.resources.adjust("system/battle", plan["resource"], -plan["cost"])
            if actual_paid!=-plan["cost"]:raise ValueError("deployment cost payment must be exact")''';assert old in s;s=s.replace(old,new,1);p.write_text(s,encoding='utf8',newline='')
    rows={str(p.relative_to(OUT/'ark_sim')):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/'ark_sim').rglob('*.py'))};core=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();print(json.dumps({'core':core,'candidate':str(OUT)}))


if __name__=='__main__':main()
