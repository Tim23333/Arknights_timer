# 显式状态机重启与技能时钟

第八章塔露拉的`switch_mode_restart_fsm`源模板同时要求切换模式与`restartFSM=true`。当前内容已能改变mode、rage属性和后续攻击选择；`behavior.transition`本身不会取消旧cast或重新建立对应技能的初始时钟。因此完整Boss仍有这一必需缺口，不能以半血数值正确替代源状态机重启。

拟增加通用效果`restart_behavior`，供任意自定义单位或状态图使用。它应明确指定目标、状态、需取消的有限ability列表、是否重置普攻时钟，以及有限初始冷却映射。效果不会读取敌人ID，不会推断章节、技能名或游戏身份。

## 源触发与期望

塔露拉原生50000HP进入半血时：先保留原HP变化和once-only模式锁存，再取消旧模式仍未完成的施法，进入对应行为状态，执行rage源Buff和显式mode赋值，随后建立所声明的初始技能时钟。已经独立发射并由原弹道策略声明retain的projectile继续自身生命周期；不可无条件删除全部弹道或Buff。

需实际反例覆盖：旧normalcast启动后、命中前跨25000阈值，旧模式未发射payload取消；命中后已经launch的projectile保持其原retain策略；新half攻击与技能依新模式执行；控制/死亡/复生回调期间重启不能让旧代任务复活。

## 参数与验证门

建议效果只接受以下显式参数，不设全局隐式重置：

- `abilities`：非空、唯一、有限的ability ID列表，必须由目标实际拥有；纳入内容依赖闭包。
- `reset_attack_clock`：严格bool。
- `initial_cooldowns`：键必须属于声明abilities；值为有限非负秒，按当前`time.quantize`规则转换；不读取游戏专用数据。
- `reason`：非空、有限长度字符串，只作trace原因。
- `state`：声明状态图中真实存在的状态。

所有schema、依赖、目标拥有关系、clock转换和状态存在性都须在变更前验证。一次效果由同一个事务包住cast取消、owned Buff/channel清理、状态退出/进入、资源变更、时钟重置和事件。状态回调第二步失败时，world、pending、RNG和事件全部回滚；回调若导致目标退休/状态代改变，剩余旧目标clock操作停止。实例私有mutation也需`finally`清理。

已发射弹道是否保持由原projectile/attachment独立策略决定，不能为实现重启偷偷改变所有旧弹道语义。没有显式restart效果的旧transition、旧关卡与自定义内容必须保持默认行为。候选需要自身完整V2套件、0-1／自定义公式基线、无选项差分和独立实际反例后才推广主底座。

隔离实现已落地在`unpack_work/campaign_behavior_restart_v1_candidate`，当前实现身份为`cba02a10cbf6e4f2736c2ee65386bd22a0cb11b04a0a8a9ed91518ed3f78fb31`，父版本为26c47。新增7个文件差异（其中一个新领域模块），主3992未修改。

新效果的23项实际作者检查通过，包含事务／RNG／owned Buff释放失败回滚、回调中退场停止、递归私有guard清理、拥有关系、已知self引用编译门、合法技能自重启、真实Talula预发射取消和已launch弹道保留。证据见 [final_gate_v3](../../validation/campaign/chapter08_behavior_restart_v1/final_gate_v3.json)。源旧版本counter在半血后仍launch30保留为 [counter](../../validation/campaign/chapter08_behavior_restart_counter_v1/counter.json)。

无选项三场景比较见 [noopt_v2](../../validation/campaign/chapter08_behavior_restart_v1/noopt_v2/verification.json)：所有状态和事件值相同，只有实现摘要、运行摘要和新增capability影响的程序摘要变化。旧工具原只允许runtime摘要导致失败，该记录保留，不当领域差异。自己的1219完整回归88424与0-1／custom基线43714已启动；独立复核尚待完成，不提前推广。

Talula源消费者新 [talula.restart.v3.reference.json](../../packages/campaign/chapter08_consumers/boss/talula.restart.v3.reference.json)（869a8138...）实际跨阈值10取消旧30发射、half新40发射和7／15秒相对初始时钟220／460；已经launch30时跨阈值31仍hit33。新状态half_restart仅为内容转换的瞬时门状态，源half及原rage值不改。状态抵抗时长、完整地图环境集成与独立来源准入继续，未宣称完整Boss或整关通过。

旧072aa作者14项和44b4版本compile-preflight证据分别保留自身身份；发现技能自重启依赖循环后，新版只排除当前定义本身的restart ability引用，其余finite ID仍进入闭包。旧失败门保留，不能迁为当前版本通过。


已推广版本为联合9ad987，包含修复后的pure availability秒上下文。自己的1219完整回归c30befd6...、0-1/custom基线ee81d82e...及独立17项a8c0e414...／冻结739d2058...齐后，Root精确8file推广c5441d2ea99cf2c0f1fe5f8960d37ae23cce01a77c6f72d5b30ad34bee8f7666。原3992备份保，候选cba（继承seconds缺口）保自己通过证据但未推广；当前主接口来源可用。动态寿命和Rebirth新自身Buff权限未包含在此次推广中。
