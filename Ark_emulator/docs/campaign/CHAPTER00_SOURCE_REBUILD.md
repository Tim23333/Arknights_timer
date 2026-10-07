# 第0章完整原生来源重建

0-10／0-11仍属于36关目标，未登记正式全程。早期m12投影只保留历史，
新装配基于固定56完整原LevelDataJSON与原StageTable，不从旧零坐标投影运行。
来源计划 `chapter0_source_prepare/source.plan.v3.json` 保留原35／37主波次出生、
DP10、8槽位、原地图／路线／runes及STORY／敌情显示动作；没有NPC或原分支。
运行时唯一统一数值覆盖为基地生命99999，固定队伍和敌方HP不改。

8敌人变体的精确prefab／Spine／原拥有节点均已提取并逐SHA锁定，
7个物理MeleeAttack保留INPUT_TARGET=2，按实际blocker施法，
原命中帧为10／12／19／18／10／12／12；完整动画周期、基础间隔、
阻挡体积、阵营索引与lifePointReduce保持。Yokai实际FLY、ATK0、
EmptyAnimatedAbility及空attack／trigger节点保留，未补造攻击。
当前原免疫字段以source已定义值消费；未定义缺省及选择细节仍需明确参考政策。

V1实际8场景完整CP/head通过，独立26CP的原生基础数值、阻挡、无目标、
飞行及公开退场／新部署通过。首次“全部动画时间除以1.25”的七个预期失败保留。
源dump显示TimeMode0=FROM_ATTACK_SPEED、MIN_ANIM_SCALE=.1，
六个节点动画上限1.0，wteeth原float32上限1.100000023841858。
V2用14个可自定义windup／duration规则消费这些字段，独立17检查／16完整CP-head通过；
Root另14场景全部通过，保旧v1字节与所有旧期待。
除数／上限模型沿既有m26可替换政策，GetDuration/ApplyAttackTime原方法体未恢复，
中途slowdown与选择tie时序仍不声称客户端已确认。

两份故事原文已提取：0-10为3个PopupDialog，0-11为2个，各有Blocker fade.3。
新装配逐原节点emit／逐popup外部ACK，保完整原text／parameters和.3逻辑延迟、
拥有控制期间输入锁；原UI暂停与人类点击等待时长未恢复，logical继续策略明确列参考。
禁止将整条story改为立即noop来消除控制依赖。

新stage.v2已编译但尚未第三方整关准入。当前短前缀与旧first8可行性计划
只支持其有界范围；正式whole需要全12人的槽位安全撤退／部署计划、
原DP保守资金、技能与召唤物公开尝试、动态driver实际ACK顺序，以及来源独立审阅。
接受／拒绝均记录，不能注入资金、提高槽位、复活或修改HP以取得通过。
最终还需完整终局、源人口账、磁盘CP续跑和从头head，完成前不增加15/36。
