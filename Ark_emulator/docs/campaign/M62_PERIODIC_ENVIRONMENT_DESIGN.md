# M62：随机周期地块与无来源伤害接口

通用周期生产与无来源结算现已组合为冻结M73候选，首21项作者测试和八原生格2项源消费测试通过；主目录仍为M68。独立复核发现正常受伤事件回调不能及时改变下一目标，修订M75正在开发。因此M73仅保上述明确测试范围，不能签回调链或4-9完整关卡。

实际8格模块见 `packages/campaign/chapter04_environment/volcano.reference_module.json`（SHA `91e2f39a2e6c492bc0da90fcb65a21e0f951bdb3abdb3306d1d48d15193c1033`）。完整原始动作与advanced开关、13/19/700黑板、原生两个Collider保留；格投影、战斗政策、首次抽样及环境归类是明确可替换模型政策。源消费报告见 `validation/campaign/m73_environment/volcano_source_tests.json`，其中没有49出生或全关完成声明。

实际输入来自冻结环境源 `packages/campaign/chapter04_environment/source.reference.json`，SHA `148a5a8648801f8c7eee655d5c0daa1f4f7469cefe3abd2d304dcdc33a121dc8`。4-9八处 `tile_volcano` 的黑板为damage700、cd_min13、cd_max19。UniformRandomTrigger的preDelay=-1、defaultInterval1；CastTile的动作是PURE类型NoSourceDamage，ignoreForSp=False；其sourceSide0、targetSide3、motion1、category1、onlyCombatEnemyInExtraRange1、injectEnvDmgFlagToBlackboard1及两个真实Collider都保留。原始字段和模型政策需分列。

PRTS地形说明确认周期参数决定热泵真实伤害。[地形参数说明](https://prts.wiki/w/%E7%89%B9%E6%AE%8A%E5%9C%B0%E5%BD%A2/trapper/tilesformat.json)。初计划把该伤害提示为arts是未验证提示，不能用于实现。

## 通用运行结构

新增与静态占格Buff分离的 `periodic_effect_field` profile。旧 `tile_field_owner` 的不可移动、不可注入攻击／行为规则保持。周期系统使用显式运行状态与调度任务，不把地块伪装成干员或敌人；每个原生格保存独立身份、原始黑板、触发计数、当前计划、任务ID、算法身份。初始化及重载后顺序一致，检查点保存真实计数和任务。

建议profile数据包含 `trigger`、`membership`、`effects`、`expected_blackboard` 和 `origin`。引用闭包收集实际规则和effect依赖；编译严格拒绝未知字段、错误合同、未绑定黑板与非法数值。全程结束后停止触发并取消待执行任务，不能影响关卡完成条件或继续消耗随机数。

`field.trigger` 为纯合同，输入运行事实、完整黑板、显式参数和已采集样本，输出严格enabled及下一次延迟秒数。内核负责按内容指定stream/count采样，完整记录随机事件，再将样本传入规则；提供器不得读取World、隐藏抽随机数、缓存跨tick值。标准示例采用 `min+(max-min)*u`，但第一周期preDelay=-1的分支、随机流、量化和同帧排序均需声明并分别测试，不能从字段名假定原生正文已恢复。

范围规则使用新 `field.members` 纯合同与实际资格projection。当前参考内容分别表达本格我方／敌人单位与四正交邻格内被阻挡或攻击中的敌人，保持ground motion1/category1。`onlyCombatEnemyInExtraRange` 不能仅凭字段名证明blocked-only；blocked、attacking、blocked_or_attacking三政策分别实测且可替换。真实root collider1.710000038与extra range0.709999979不直接等同中心点格半径；当前格投影仍待原生范围核对，不让纯geometry bypass活性、显隐或target-free。

## 无来源伤害

伤害请求需要明确origin及归因数据；不能为方便调用而给地块虚构ATK700、发送有干员来源的攻击、用modify_resource直接扣HP或让环境击杀触发干员自身击杀天赋。

`damage.pipeline`仍是可替换数值合同：示例读取effect中固定值700，真实伤害不读取DEF或RES；保留target after hooks以消费无敌、护盾、承伤分配、比例或限伤规则。无来源路径不运行攻击者before hooks、不采样攻击者命中／暴击、不获得攻击回复SP。事件source为None，origin保存真实地块及触发身份；目标受击SP由显式ignoreForSp=False政策消费。死亡事件保留环境来源，普通生命周期、死亡天赋、尸体弹道及关卡计数依次正常执行。

给目标伤害后是否得到SP、击杀是否触发所属召唤物／干员计数、生命耗损与damage accepted实际HP损失都必须用受控场景核对。不能用pipeline原始700覆盖HP只剩100时的实际损失100，也不能把ENV黑板注入和原节点_isEnvDamageFalse混为同一个已证明开关。

## 必需验证

- 独立种子样本、13至19秒分布、首次与后续周期、确定性row/col初始化与两地块独立状态；替换规则确实改变间隔，错误／NaN／零负延迟完整原子回滚。
- 700真实伤害不受DEF／RES影响；target无敌／盾／分配／限伤仍消费；source为None，无虚构攻击者before hooks或击杀奖励；目标受击SP按源开关执行。
- ground／fly／category、位于本格、被阻挡邻格、未阻挡邻格、hidden／target-free、移入移出、同tick状态变化及死亡后重新资格读取。
- 完整事件、RandomStreams、World、任务与计数的磁盘续跑／公开命令回放一致；没有profile时父／新旧模型除版本身份全部相等。
- 4-9源八格实际组装、全部49次出生及12人公开操作完整运行；该关短测或其他地图不能签其全程。
