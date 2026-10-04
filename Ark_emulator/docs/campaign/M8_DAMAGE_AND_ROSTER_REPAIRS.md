# 当前整合内容的两处伤害绑定修复

固定12人及36关目标继续执行；本批保持 primary core 的 M8
`f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`，修复在新的内容wrapper中。
旧内容、旧胜利、正在运行的恢复/回放和原反例各自保留输入身份，不能迁移成新内容通过。

## 塞雷娅的法术增伤

独立审查实跑发现，M7原整合包的 `buff/demkni_member` 虽将目标 `arts_factor` 变为1.55，
但正式默认伤害链没有读取它。艾雅法拉实际面板对应的同一法伤packet在S3前后都是809.4，
独立预期1254.57；旧recipe夹具对自己的probe effect单独绑定pipeline，因而掩盖了整合遗漏。
原失败及原来源见 `first_model_saria_integration_probe.json` 与 [首关范围审查](FIRST_MODEL_ACCEPTANCE_SCOPE.md)。

`tools/build_m8_damage_integration.py` 生成 `squad.m8_damage.json` 与两个 `level_main_00-*.m8_damage.json`。
目标光环成员绑定 arts-only `damage.after` hook，使用已有通用settlement_scale按原生选技倍率1.55
同时放大结算amount和该目标HP allocations；其它资源allocation不放大。
同族 `arts_damage_taken` 选最高priority一次，与铃兰fragility独立叠乘。
原 `arts_factor` 保留供属性观察，正式伤害无需每个攻击者手工选择专用pipeline。

该wrapper还核对每个unit的完整配置及exact native选技，再补齐12个selected ability的
`metadata.native_skill_id`。这是审核身份字段补证，不改角色技能。
`client_pending`、旧pending历史和formal=false全部保留。

实跑 `test_m8_damage_integration.py` **10 passed / 4.54秒**；独立审查另实跑同10项 **4.59秒**。
覆盖原反例、新伤害、physical/true不变、MRES、离开、脆弱叠乘、重复同族、命令checkpoint/replay、
自定义HP+shield分配（HP15.5、shield只耗1）和全部12选技身份。
独立使用同一probe读取新包实际得到809.4→1254.57，详见
[独立修复复核](M8_DAMAGE_INTEGRATION_REVIEW.md) 及 `first_model_saria_m8_damage_probe.json`。

## 雷蛇护盾

canonical整合审查又确认，S1在默认伤害链未绑定抵挡效果；即使shield_charge=1，
源ATK100仍造成physical5/arts90/true100，charge没有消耗。
原失败保存为 `canonical_lisk_counterexamples.m8_damage.json`，不把失败重新标成通过。

原生 `damage_block_once` BSON实际为 ON_TAKE_DAMAGE 执行 BlockDamage 后 FinishBuff；
damageType/applyWay没有过滤。原始TextAsset SHA为
`0c438b57b176e0fa430b5b982a58c7b524f4121aa8dbab33d3e647aa0fc1ee59`。
新wrapper保存确切源文件/hash、子文档base64/offset/SHA和parsed动作，不只按模板名称猜功能。

`tools/build_m8_roster_corrections.py` 在damage包上生成新的 `squad.m8_roster.json` 和两个
`level_main_00-*.m8_roster.json`，给S1 Buff接收方after hook：所有伤害类型一次仅消耗一个charge，
不重复计算默认pipeline；DEF+100% Buff继续8秒。未被挡packet仍走原pipeline。
当前明确模型策略是零HP损伤packet耗盾但不返防御/天赋SP；native事件优先顺序仍列client_pending。
带自定义转移分配的shield仲裁也保留待处理边界。

雷蛇S1自身属于防御回复，源increment1，天赋另有自己1/邻友1。两条独立源均保留，
普通受击自身合计2SP；不能只看到天赋BB1就错误删除基础恢复。
当前模型9次有效受击获得18SP，自动支付后第10次由盾抵挡。

`test_m8_roster_corrections.py` 实际 **7 passed / 23.61秒**：三种旧反例与新单次挡伤、
自2/邻1、blocked零邻友恢复、9次自动支付/第10次挡/cp及命令replay，
tick240半开终点解除DEF/未用盾并恢复普通SP2。邻友夹具明确将canonical Ptilopsis初始SP设0，
避免把固定队伍的初始SP与计数上限误认为talent增量；未修改其技能定义或实际基础面板。

## 验证身份与后续

上面17项为M8完整1002项以后新增的整合定向测试，没有声称执行了新的1019项全套。
旧0-10在当前core已35born/35kill/0leak，顺序checkpoint/replay尚在运行；
旧0-11探索实际37born/37kill/0leak、12commands accepted、timeline complete，
`checkpoint_resume_equal/replay_equal=null`（no-replay探索）。

damage版0-10的完整/恢复/回放与0-11的完整探索已另启新输入验证。
roster版需要独立三人见证复核后纳入下一冻结批次；当前长程脚本只部署六人，没有用未部署雷蛇给护盾盖章。
后续继续为陈/雷蛇/铃兰及凯尔希/夜莺/温蒂建立同canonical配置的独立闭包。
正式关卡仍0/36，完整原生干员仍0/12；source versions与client准确性独立报告。

```powershell
..\.venv\Scripts\python.exe tools/build_m8_damage_integration.py --check
..\.venv\Scripts\python.exe tools/build_m8_roster_corrections.py --check
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m8_damage_integration.py tests_v2/test_m8_roster_corrections.py -q
```
