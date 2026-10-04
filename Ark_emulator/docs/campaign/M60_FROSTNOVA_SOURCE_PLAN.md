# M60：第四章来源独立审计与霜星依赖计划

原来源不修改：`chapter04_plans/source.plan.json` SHA `2b9a49412d64945eacca82282866b4c8b12eb11f5676dd831878a51ec01a9086`，`chapter04_sources/native.reference.json` SHA `3e392d80d000e27a50f11f2f33b0fa0f6be35dc1e91d7e321e2b9cf9681c4603`。新独立审计 `tools/audit_chapter04_boss_sources.py` 生成 `packages/campaign/chapter04_boss_plan/source.reference.json`（SHA `7ad2fb46b3e281711b6faf8b7a3bacfb9df6bc11ff32212a8439d8925d6893ec`），build 和 `--check` 均实际成功；没有创建任何 Runtime，也没有全关执行或审批收据。

工具对两个原始 native level JSON 重新统计 waves/fragments/actions，独立把 buildable/passable 枚举转为格数据，核对全部原生文档、49/43次出生、使用路由、控制、原始flags、索引、runes 与 predefines。13个实际 enemy prefab 和6个 projectile 均重新按 GameObject/Transform树读取 Unity typetree；组件 pathID、MonoScript类与原始字段全相等。23条具体检查保存在新审计中。BSON以原始 TextAsset长度与4字节对齐读取Script，用新有界解码器在实际document偏移解码，文档字节SHA与结构都核对；不调用源builder的验值函数。`BslimeTalent_1` blackboard `key=projectile/valueStr=projectile_bslime` 的依赖确实包含在6个projectile内。demon的 `NoPreOneshotAnimation` 两支保留：Attack帧27/时长45，Attack_NoPre帧15/时长33，结束Attack_Idle帧30；不凭动画名字猜分支选择。

精确 Boss VID `enemy_1505_frstar@0/9d1e3d01ef79ae3e`：HP25000、ATK420、DEF250、RES50、射程2、攻击间隔3.7、moveSpeed0.5、重量5、漏怪扣基地2。数据中stun/silence/frozen/levitate immune为True；普通攻击及技能的原始状态字段保留，不由“冰属性”文字添加第六章寒冷/冻结。

2026-10-03实际读取 [PRTS霜星](https://prts.wiki/w/%E9%9C%9C%E6%98%9F) 的级别0与 [封印的地面](https://prts.wiki/w/%E5%B0%81%E5%8D%B0%E7%9A%84%E5%9C%B0%E9%9D%A2)。以下为小范围来源摘要，不复制整页；其余数字由已锁定表与原始字段支持。参考规定首次倒地5秒后回复全生命并提升ATK50%，冰环造成150%法术与8秒ASPD−50，地块技能随机封两格并击倒其上单位。封印地面只占位置、没有受击区域，不重写地形。当前用户明确参考网站与固定数据优先，后续统一实机反馈单列。

RebornTalent exact PPtr `-5435638963227298068`：maxRespawnCnt1、modeIndex0、keepAlive0、hpRechargeRatio.5；表 BB `reborn.duration=5`、`reborn.atk=.5`。参考的满HP与serialized .5是实际差异，不能互改来源。声明profile选择有效maxHP×1.0，保留可替换ratio参数与raw.5。ATK提升420→630。源 buff modifiers 为 ATK1/MULTIPLIER1，BB加载；不把其blackboard `mode=1`伪造为不存在的UnitMode1。初始Passive `frstar_c` 有 `abnormalComboImmunes[0]`（沉睡组合），参考规定重生后失去；原 retainedBuffs列表为空。原生 Reborn/AssignData/ModifyHpRatio 等dump只有空方法声明，不是正文证据。

普通 RangedAttack `_waitForAttackEvent=1`、INPUT_TARGET2、法术scale1；其Attack动画有17、28两个OnAttack。ArcticBlast同样播放Attack，但独立节点 `_waitForAttackEvent=0`、raw preDelay.9330000281333923≈28帧、FROM_OWNER1。声明普通首事件17一次，技能由preDelay28驱动；第二个动画事件不是两发普通攻击的证明，原始两事件全部保留。ArcticBlast表CD/init8.5、priority1、scale1.5、trigger radius2.5、AS−50、duration8。源模板Buff life4与表/参考8分列；源Hit motion3与参考不可对空也分列，声明使用参考ground-only。S1 projectile没有运动组件，speed0/reference为源中心半径2的法术范围，源mount GROUND7及CircleCollider radius2保留；同一合法捕获主目标在半径2外、2.5内仍应按参考强制包括。

IceShield表CD/init30、priority2/max_cnt2；EnemySkill→TileTrigger→TileSelector链与同GO SpawnTokenOnTileAbility真实恢复。Skill映射到Skill_1帧55；Reborn映射Skill_2时长216帧，和表重生5秒不是同一时钟证明。TileSelector filter2枚举是EXCEPT_CHARACTER、alwaysRandomInTheEnd1/max2。其完整原始配置保存；该filter与参考能够击倒占格玩家的选择解释仍有方法体缺口。声明可替换“半径2内可部署格，min(2,n)无放回均匀采样”数学profile，不称原生随机流、分布或seed算法已恢复。query应纯且不抽样，真正接受cast才消耗RNG。

技能actions实际为InstantKill TARGET、skipRebornFalse、不是damage。token源 inst 为 `trap_004_iceblock`、E0L0；固定2026表没有该key，新审计明确False，没有猜成表已定义。官方2025固定tokens资产读取到exact Trap/TrapMode/EmptyAnimator，category2、SideType.ALLY1、没有hit collider。注意SideType1是ALLY，SideTypeIndex1是ENEMY，两个枚举不能混。root `_rewriteTileOptions=0`，所以TrapMode存储的buildable0/passable2未启用，不能把黑冰做成FLY_ONLY障碍。声明引用网站HP100/ATK0/DEF0/RES0，以无DP技能spawn且capacity0的deployable占格、不可手撤、没有普通命中区域、永久保留；敌人仍可走，原始未启用TileOptions保留。Source-retire是否保留、ownership与具体constructor仍显式配置，不虚构表来源。

最小扩展方案先交Root审阅，暂未写M61核心：

1. 通用 delayed rebirth component（不是官方ID分支），显式health resource、max_count、delay、restore_ratio与on_begin/on_finish/保留buff名单。第一次真实HP0写World pending状态及owned job；同一actor保留managed人口，不发布combat.kill/retired，不创建第二actor。down阶段activeFalse/HP0，停止移动/攻击/阻挡/选中与恢复。恢复前复验generation、生命周期与终局，取消不得ghost复活；全阶段事务回滚、owned tasks、CP/replay。
2. source与reference驱动的on_begin清除旧效果/解除阻挡/中断自己cast；on_finish有效上限×ratio回复、ATK+.5与睡眠免疫清理，重置敌技能初始CD，第二次HP0才真正death。callback必须每步复验，不能在回调死亡后无条件重写alive。倒地表示模型managed/pending状态，不拿raw keepAlive0偷换为已恢复的原生布尔语义。
3. 通用敌技能clock/priority arbiter：8.5/30初始CD、技能期间暂停、重生重置，与攻击时钟互斥；numeric priority方向、cast窗口与队列正文未知需声明profile。技能Body选敌、timing、target capture均从实际节点绑定。
4. 纯tile eligibility与采样接口，现有live map getters为输入；真实cast随机选格后逐格InstantKill/lifecycle与token无DP生成。kill有source/cause与skip-rebirth策略，不能冒充高额true damage。占格禁部署与无hitbox的资格规则独立于地形通行。

需要新增通用状态/免疫消费者时先形成明确配置；不能因固定队伍没有触发睡眠或没有击倒Boss而省略初始/第二阶段差异。所有缺口、source版本差异与客户端反馈分列，推进不会等待未恢复正文，但不会把声明模型标成实际客户端已验证。
