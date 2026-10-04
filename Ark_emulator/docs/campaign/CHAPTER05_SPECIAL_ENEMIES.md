# 第5章碎岩攻坚手与近战法师

固定源为 `chapter05_sources/native.reference.json` SHA `323baee04eca79f6e750cf45d460ffe678667c1614763814436402e8187badd5`。新模块 `chapter05_units/special/model.reference.json` SHA `cbc8ad5806e5ae7801e9d58e7d92542ab45567b42675a82a47c8b7cad4195579`，通过 `tools/chapter05/build_special_units.py --check` 字节复核，主Frostv5 core7a04执行，无新增核心分支。

碎岩攻坚手精确level0：HP10000／ATK1000／DEF1000／RES0，间隔3.5秒，普通与StunCombat共用Attack动画，OnAttack28帧。DB攻击回SP上限2、初始0、每次攻击+1；技能消耗2、initial/CD1秒、stun7秒。内容使用真实付款与每次接受攻击的单次回复，明确技能攻击也回SP；技能眩晕在接受伤害后应用，资格按投影flag0／免疫处理。ReadyEnemySkillEffect保为表现字段，不能替代实际SP或Buff执行。

近战法师精确level0：HP4000／ATK400／DEF250／RES50，间隔4秒、射程2，OnAttack21帧，法术弹道源速度10、寿命10。两个模式槽实际 `_combat` 与 `_attack` 指向同一PPtr4029926580866268503，只执行一个法术伤害包。SourceCombat2硬筛当前阻挡单位并同时满足原目标侧别／运动／类别／状态和几何，不能用仇恨分数跨过实际阻挡身份。

作者3项实际通过27.43秒，报告 `validation/campaign/chapter05_special/author_actual_blocking_order.json` SHA `a07b326e99cb0248fdeb53a4ac7ddea24c9c01a5ba0961caa240b0ee2ad363a2`：hammer真实两次普通攻击SP2后付款2，第三次攻击眩晕7秒、单次回复SP1，目标不能继续阻挡；有源眩晕免疫目标仍接受相同伤害／回复SP1但保持阻挡。lunmag只一次法术包、对RES25目标300、frame21＋3刻飞行，完整检查点及从头回放相等。

最初hammer测试期待初始cast0；实际标准behavior在movement阻挡结算前运行，blocking.changed@0之后下一刻cast1，因此源实际cast1／106／211、hit29／134／239。原错误期待报告467c5f9a...保存，新断言明确每次cast相对命中严格28刻；没有改source帧、属性或底层时序，也没有声称此初始化先后已与客户端核对。

ASPD前摇、动画持续／钳制、SP与技能伤害接受规则、实际相机／collider和来源版本对齐均明示参考政策，待独立新夹具复核与用户后续反馈。独立审核和第5章整关尚待完成，不将本模块测试作为5-9或5-10完成证明。

## 独立远程反例与修订

原模块cbc8ad58...独立7项中6通过、1项真实缺陷：近战法师未阻挡时距离1处合法地面目标没有任何施法／伤害，behavior错误共用blocked_target=True；源确有Ranged SelectorTrigger且两个模式槽同PPtr。独立失败报告3a10b314...保存。

新 `model.ranged_guard.reference.json` SHA `a491491f577f5842660ddbcff3a6eda0cfab1fff9f4994c1cb04f107bc6463dc` 只修lunmag的触发行为为blocked_target=False。真实阻挡时SourceCombat2硬目标资格和原typed筛选保持，未增加第二个攻击能力；hammer全部SP／Buff／伤害不变。

Root也确认原作者lunmag断言 `expected[:len(hits)]` 过宽，零事件可能误通过，旧报告仅保真实狭窄范围，不作为远程触发证据。新作者断言硬要求hit24／144两包300、两次attack.accepted并运行至145；三个测试实际通过28.47秒，guard绑定源码、正确模块和测试身份的新收据 `author_ranged_guard_bound.json` SHA `44d0b55d20ade178f44cdc25d70aa7487ed0309d7e084180757af3cc7ab7f77a`。独立原七项断言在新模块重跑仍待完成。

## 首刻阻挡与目标捕获

独立原七项在a491上实际5pass／2fail，报告ad12856d...保留：首次远程施法在普通movement阻挡结算前发生，虽之后blocker关系为3，cast捕获的高仇恨邻居4仍受击；不可选中的实际blocker也被邻居替代。没有通过改期待为邻居命中来认可这个SourceCombat2错误。

新通用 `ability.activation.settle_blocking` 为严格布尔可选字段，在捕获前运行现有实际阻挡结算和可替换数值规则，位于完整施法事务内，失败回滚World／任务／事件／随机，保持原阶段顺序与无特性行为。当前独立候选 `campaign_selection_settle_v3_candidate` core `30e4cdfadc5a98eb59da20d89591f5f5d3d6acc8f2d9a997df5e761d759fb49d`，基于Faustc6，只改schema／abilities两个文件，冻结2092d95a...。

新内容 `model.selection_settle.reference.json` SHA `fa314fcf5e46ddcef792ced3f1f7f86cc1586d7f74e5915af305f270dff55b8d` 为lunmag显式启用捕获前结算。原七项断言AST全部相同，只换modulepath／pin，在新核实际7pass50.49秒，7272bbf0...；typed字段／失败事务／显式False及原技能／空间兼容44项通过2.73秒。独立新边界审核及组合验证待完成，未推广主目录或迁移旧证据。
