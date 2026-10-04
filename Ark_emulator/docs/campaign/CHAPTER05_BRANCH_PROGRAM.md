# 第5章分支程序消费者

浮士德 `SummonBallis` 的原始 `AnimatedActionToOwnerAbility` 使用Skill_2动画、OnAttack27帧，SerializedState实际为 `MoveNextLevelBranch`，DB黑板branch_id=`faust_ballis`。5-10原始分支包含7个phase、10个 `ACTIVATE_PREDEFINED`，依次激活既有 `trap_007_ballis#1` 至 `#10`，最后两阶段分别激活2、3个装置。源计划固定 `c33c5a199fce73ef7b7524e0d29e59eeca6eb69a7f2ebd7d8c253634b050bee6`。

`tools/chapter05/build_faust_branch.py` 输出 `packages/campaign/chapter05_boss/faust/branch.reference.json` SHA `2447fa97a705ab7fa168fbef6dfa39ed5c2d2c9c1d6f2fb1864d56804bb55c66`，保完整原branch并严格核对count、interval、管理、随机、预览与阻挡字段后转换。没有将unknown动作或缺少注册对象写成空emit。

新通用候选 `campaign_branch_program_v3_candidate` core `d2c7419cd39d3694bb47da2fe28bcf8359d80e0b119db96179ca34943b78e5c4` 基于冻结Frost组合v5，仅新增显式 `scenario.branches`、`advance_branch` 操作和真实phase调度。cursor、generation、running／idle／stopped、剩余动作、实际任务ID和due／consumed均保存在World，进入检查点与回放。数量、延迟、效果、loop、phase资格严格校验；数值延迟通过可替换 `time.quantize`。

每次请求推进一个phase，前个phase未完成时拒绝新请求；一个action的所有effect原子提交，重复激活导致错误时前面激活也回滚。终局取消保留剩余数量及stopped，不宣称未执行动作完成。已经接受的phase在请求源退场后继续，除非战斗终结；这属于明确参考政策，不冒充已恢复原生分支调度正文。

11项作者实际通过1.63秒，收据 `validation/campaign/branch_program_v1/author_v3_with_source.json` SHA `2a95c611e08c5a729a532267fbe0a3d9db00cc881a5f599eb8974b2aa4cc9210`。源7phase／10对象测试真实公有施法、注册激活、运行中检查点和从头回放一致。测试中的注册对象只验证通用调度，尚不是实际弩炮攻击消费者；浮士德本体、弩炮技能、弹道／碰撞、独立反例复核和5-10整关尚待完成。

最初未知key负例被原Compiler在编译阶段拒绝，后续用两个合法同key激活验证实际运行回滚，原失败夹具报告保留。独立反例复核进行中，当前候选未推广到主目录，标准4-10仍使用冻结Frostv5，不迁移其回放身份。
