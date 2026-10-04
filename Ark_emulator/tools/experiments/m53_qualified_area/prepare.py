from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT.parent/'unpack_work/campaign_m48_chapter02_area_integrated_candidate/ark_sim';DEST=ROOT.parent/'unpack_work/campaign_m53_qualified_area_candidate/ark_sim'
def change(name,old,new):
    p=DEST/name;s=(BASE/name).read_text(encoding='utf8');assert old in s;p.write_text(s.replace(old,new),encoding='utf8',newline='')
def main():
    change('domains/providers.py','from .request_transforms import request_field_transform','from .request_transforms import request_field_transform\nfrom .qualified_areas import qualified_cell_offsets')
    p=DEST/'domains/providers.py';s=p.read_text(encoding='utf8').replace('    "ark.area.cell_offsets": ark.area_cell_offsets,','    "ark.area.cell_offsets": ark.area_cell_offsets,\n    "ark.area.qualified_cell_offsets": qualified_cell_offsets,');p.write_text(s,encoding='utf8',newline='')
    change('domains/effects.py','''                    result = self.ctx.calc("area.members", {"center_position": position,''','''                    area_extra = {"ability": ability, "effect": effect}
                    member_rule = self.ctx.rules.rules[effect["membership_rule"]]
                    if member_rule["implementation"].get("provider") == "ark.area.qualified_cell_offsets":
                        from .qualified_areas import projection
                        options = {**thaw(member_rule.get("parameters", {})), **thaw(effect.get("parameters", {}))}
                        area_extra["area_selection_states"] = projection(self.ctx, source, candidates, options)
                    result = self.ctx.calc("area.members", {"center_position": position,''')
    p=DEST/'domains/effects.py';s=p.read_text(encoding='utf8').replace('extra={"ability": ability, "effect": effect})','extra=area_extra)');p.write_text(s,encoding='utf8',newline='')
    change('content/capabilities.py','''        if item.get("op") == "area" and item.get("membership_rule"):
            require("area.members", path+".membership_rule", explicit=item["membership_rule"])''','''        if item.get("op") == "area" and item.get("membership_rule"):
            require("area.members", path+".membership_rule", explicit=item["membership_rule"])
            member_rule = definitions[item["membership_rule"]]
            if member_rule["implementation"].get("provider") == "ark.area.qualified_cell_offsets":
                from ..domains.qualified_areas import validate_parameters
                options = {**member_rule.get("parameters", {}), **item.get("parameters", {})}
                try:validate_parameters(options)
                except ValueError as error:raise ContentError(path+": "+str(error)) from error
                require("targeting.eligibility", path+".eligibility", explicit=options["eligibility"]["rule"])''')
if __name__=='__main__':main()
