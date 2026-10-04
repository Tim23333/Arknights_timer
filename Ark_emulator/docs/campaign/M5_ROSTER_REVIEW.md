# M5 独立复核记录

2026-10-02，本轮只读复核生产实现及整合工具；仅新增独立测试与本文档。使用真实 V2 Compiler/Engine，无空 handler、模拟器 stub 或 V1 战斗运行时。未生成正式审批收据，未提交或推送。

复核结论：发现的两项阻断由 root 修复，独立预期保留不变，最终定向验证 **22 passed in 6.00s**。这证明下述模型合同，不证明原生回调、完整干员、正式关卡或客户端一致性。

## 复现与修复

| 问题 | 独立实际输入与原失败 | 修复后的合同 |
|---|---|---|
| 自动替换攻击未按付款 owner 检查资源 | `test_automatic_replacement_readiness_honors_battle_cost_owner`：技能是 manual + auto_when_ready + replace_attack，费用为 battle.dp=1；源只有 hp/sp，战斗有 DP2。编译接受，首次 advance 在 `ark_sim/domains/abilities.py` 的 tick readiness 调用 source-only payment_plan，抛 `resource 'dp' is absent on 2`。 | `AbilitySystem._cost_groups` 在 start 和自动 readiness 共用。首次攻击扣 battle DP 至1，两个目标 HP100→80。未为 source 虚设 DP 来绕过问题。 |
| 派生帧可与自己的原始证据矛盾 | `test_forged_frame_binding_cannot_override_its_own_raw_payload_evidence`：临时目录复制真实来源 JSON，同时把 Night mode0 front/back binding event.frame 27→0，保留原始 skeleton bytes、hash 与解析证据27。此前 units.build 接受并生成0秒治疗；单改一脸会被前后相等校验拒绝，因此必须同时改两脸才复现真实缺口。 | `tools/build_campaign_units.py:build` 从当前资产和私有受控 reader 重建完整 bindings，并与传入 JSON 精确比较。两脸同时伪造明确拒绝为 source/evidence identity mismatch。仅重新计算被篡改 JSON 的 SHA 不足以通过。 |

两项均由生产工具实际失败揭示，修复由 root 完成；复核者未改生产代码。第一次长一点的组合验证恰逢 root 修改生产文件，replay 正确拒绝 runtime fingerprint mismatch；该运行不算通过，随后冻结身份下重新完整运行。

## 验证范围

- `source|owner|battle` 同一次技能付款分别扣 child.ammo、其真实 owner.sp、battle.dp；不误扣 child.sp。owner 资源不足时，其他付款、cast、任务、事件和检查点全部回滚。
- 时间曲线技能在施放采样 ATK36，延迟65帧后 buff 已到期。`at_cast` 仍造成36伤害（HP64），`at_hit` 造成基础10伤害（HP90）。两者各自在中间检查点恢复和输入回放保持完全一致。
- owned selector 的成员在0.5秒寿命结束后，于配置0.1秒检查周期清 SP、打断已有两秒技能；40帧的延迟命中被取消，目标 HP100。恢复与回放保留 selector cache、任务和资源状态。该模型明确使用轮询合同，不声称失去成员瞬间检查。
- 将带 on_remove 的 buff 施加到另一目标，再移除该目标上的 buff，同步清理的是 retained caster 的 mode，而不是 buff 目标或移除者。root 原有半开 expiry、失败回滚和结束帧效果测试也通过。
- 真实 rebuild 的 squad 中，12名 `campaign_roster` actor 的配置、ATK/DEF/maxHP/RES 与 normalized 固定模型值逐项相等；每个选定技能 ID 保留 native 来源，能力确实存在且由该 actor 持有。没有把 fixture ATK/HP 替代正式养成数值。
- 12个基础攻击均有转换输出；Night normal 使用精确 `Attack_A` 绑定、27帧/0.9秒。全源 bindings 重建覆盖当前资产、reader/extractor 身份和派生映射。
- squad 和 base 保留 `complete_operator=false`、complete count0、所有缺口列表；squad `formal_mainline_approved=false`。选技原型的 source-backed primitiveModel、封存原文和实际可运行能力均不能自行证明 talents、native callbacks 或 fullOperator。

## 可重复命令

工作目录 `D:/Arknights/Arknights_timer/Ark_emulator`：

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m5_roster_review.py tests_v2/test_temporal_and_recovery_gate.py tests_v2/test_buff_mode_lifecycle.py -q
```

独立测试10例，root temporal5例，root Buff mode7例，共22例。临时来源攻击只修改 pytest tmp_path，未修改源资产、安装库、共享表或已有参考包。

## 冻结身份

最终验证的 V2 runtime fingerprint：

`998b0c5ee85b7d26beb95045cd0faacdf2fe6a9cf566733ea022a01c35a63274`

| 文件 | SHA256 |
|---|---|
| ark_sim/domains/abilities.py | c2cce6f9204ac85dce2456759835d97c64eca2590e47744628314ecce04b0cb7 |
| ark_sim/domains/resources.py | 3d1fa3533c8d959d324b6a8e517083fbef05588e6daee455b64683b5a05e3ea2 |
| ark_sim/domains/context.py | 2a8c8abdd110f208d6f788e9a23aeee7d141a24849596d92c0ecea949c515fcb |
| ark_sim/domains/attributes.py | f13e98b4f39ba2625457bb884467d7ff6af3f9da738ced76a4c455af8ce5343e |
| ark_sim/domains/buffs.py | 4c0b96bc382a8f09fc5a7ad66689f89ffc45f572cbc6de9e2b204156ff4a54c2 |
| ark_sim/presets/providers.py | 3e8c6442e879ab3473e7b284b1466f809b077fa4ef6b79a91f0d1b235084f4b5 |
| tools/build_campaign_units.py | 94744bf5015b6ff288df25045007d91a23b7fcdabdf2dea26cbbfcd7b4735df1 |
| tools/build_campaign_squad.py | 26b1946bb3e3b44385393c913a7da6f1ce67c91c6d8921834b502b9dd1948990 |
| tools/extract_campaign_animation_bindings.py | a9f7a2de3a6dde0f8e41cf5abbaf7d4cce6a75328e21ee294451dd84d75d96be |
| tests_v2/test_m5_roster_review.py | 359a59905b260ea739c6d5f2d3fd3cd7c5abefdb89669a3bf78699524b26115b |

身份改变后本记录保留为历史证据，不自动提升为新实现通过。root 最后全 suite、全部内容 `--check` 与同身份 baseline 是另外的证据；本报告不代替它们。
