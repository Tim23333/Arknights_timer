"""Recheck actual actor/cast gates after synchronous blocking callbacks."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_selection_settle_v3_candidate'
OUT=ROOT.parent/'unpack_work/campaign_selection_settle_v5_candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def core(root):return hashlib.sha256(json.dumps({str(p.relative_to(root/'ark_sim')):sha(p) for p in sorted((root/'ark_sim').rglob('*.py'))},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def main():
    assert core(BASE)=='30e4cdfadc5a98eb59da20d89591f5f5d3d6acc8f2d9a997df5e761d759fb49d'
    if OUT.exists():raise FileExistsError('Preserve candidate')
    shutil.copytree(BASE/'ark_sim',OUT/'ark_sim',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    path=OUT/'ark_sim/domains/abilities.py';text=path.read_text(encoding='utf8')
    old='''                    if not self.ctx.active(source) or self.ctx.state().get("finished"):
                        raise ActivationRejected("Source became inactive during blocking settlement")'''
    new=old+'''
                    runtime = self.ctx.get(source, ("runtime",), {})
                    if ability_id not in self.ctx.get(source, ("abilities",), []):
                        raise ActivationRejected("Source lost ability during blocking settlement")
                    if self.ctx.route_hidden(source):
                        raise ActivationRejected("Source became route-hidden during blocking settlement")
                    if runtime.get("cooldowns", {}).get(ability_id, 0) > now:
                        raise ActivationRejected("Ability cooldown changed during blocking settlement")
                    if forbidden:
                        from .selection import DEFAULT_STATE
                        if set(forbidden) & set(self.ctx.spatial.selection_state(source, DEFAULT_STATE)["abnormal_flags"]):
                            raise ActivationRejected("Source status changed during blocking settlement")
                    controls = self.ctx.buffs.controls(source)
                    if not controls["abilities"] or (mode == "automatic_attack" and not controls["attack"]):
                        raise ActivationRejected("Source became controlled during blocking settlement")
                    if not self._condition(activation.get("condition"), source, ability, event_payload):
                        raise ActivationRejected("Activation condition changed during blocking settlement")
                    casts = runtime.get("casts", {})
                    if blocks and any(item.get("blocks_attacks", True) for item in casts.values()):
                        raise ActivationRejected("Blocking cast started during blocking settlement")
                    if any(item["ability"] == ability_id for item in casts.values()):
                        raise ActivationRejected("Ability started during blocking settlement")'''
    assert text.count(old)==1;path.write_text(text.replace(old,new),encoding='utf8',newline='')
    out=ROOT/'validation/campaign/selection_settle_v1/freshness_repair_v5.json'
    report={'parent_core':core(BASE),'core':core(OUT),'changed':'domains/abilities.py','full_stage_executed':False}
    with out.open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
