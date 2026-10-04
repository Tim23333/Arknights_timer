# M8 Saria结算wrapper只读复核

2026-10-02，冻结core `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`。对象为 `tools/build_m8_damage_integration.py` 及三个新输出；不修改core、旧M7/M8包或旧证据，不签formal receipt。

使用先前发现缺陷的同一个独立 `tools/probe_first_model_saria.py`，仅通过CLI选择新 `level_main_00-10.m8_damage.json` 和独立新output。真实Compiler+Engine结果：相同MRES0arts packet原值809.4，S3 aura factor1.55后实际1254.57，独立预期809.4×1.55一致。新证据是 `validation/campaign/first_model_saria_m8_damage_probe.json`；原 `first_model_saria_integration_probe.json` 保留原输入下809.4→809.4的失败，不改标。

代码把source-bound倍率1.55绑定至target member的after hook，条件仅arts，group为arts_damage_taken。settlement_scale保留非health/非target allocations，缩放target health与scalar amount；独立fragility使用不同group，因此可相乘，重复同组只一次。保留旧arts_factor给观察但结算不靠全局不合格modifier读取，避免先前ghost来源问题。

实际 fresh `tests_v2/test_m8_damage_integration.py` **10 passed in4.59s**，包括原缺陷、新值、physical/true、MRES顺序、aura离开、fragile、重复同组、真实命令checkpoint/replay、customHP+shield分配。wrapper `--check` 实际成功；0-10 program fingerprint `d90c75de090729041a528abb546039fd555ca0d519785bc164aadbab139a8828`，0-11 `f76965398c44e477f4dbd4e1acd3887781704c7aba40d355e9acc8882f060145`。

另只读逐unit核查12 selected ability，metadata native_skill_id均与unit selected_skill_native_id及normalized固定配置一致，并由unit拥有。四个旧缺字段已闭合。这个身份补齐不证明机制全部执行，也不替代七门中的未部署六人闭包和正式审核收据。

旧首关/次关长程状态不能迁移成新内容通过。当前新增wrapper边界内没有新阻断；新包仍需独立闭包见证和新输入全程三路同身份artifact。原36关目标及formal0保持。

```powershell
..\.venv\Scripts\python.exe tools/probe_first_model_saria.py --package packages/campaign/mainline_models/level_main_00-10.m8_damage.json --output validation/campaign/first_model_saria_m8_damage_probe.json
..\.venv\Scripts\python.exe tools/build_m8_damage_integration.py --check
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m8_damage_integration.py -q
```
