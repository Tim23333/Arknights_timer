# 第6章固定来源准备

由固定mainline_catalog selected字段核定：内部ID `main_06-14/main_06-15`，
显示代码为6-16/6-17。不是凭记忆选择其他倒数关卡。
固定公开表提交为 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`。

6-16原生50births/8敌人变体、slots9/life3/DP10/maxDP99/moveMultiplier.5。
6-17原生1birth/1敌人变体，为slots0/life1/DP0/costIncrease9999的训练剧情关。
两关合计九个精确variant，level与override完整保留。

## 已提取的完整来源

- chapter06_plans/source.plan.json：完整map/tiles/blocks、routes、waves、计数、
  options/runes/predefines/branches和九个source属性/技能/BB变体。
- native.reference.json：九个Enemy prefab、四个弹道、PPtr/MonoScript、Spine/OnAttack、
  collider/Transform/SerializedState、BSON模板、BB valueStr及逐slot依赖矩阵。
- chapter06_environment/source.reference.json：tile_fence、tile_telin、tile_telout闭包和原路线操作数。
- chapter06_predefines/source.reference.json：trap_010_frosts、Amiya/Swallow/Blaze四个prefab，
  sktok_frosts精确skill/prefab、角色Spine/skill事件与弹道闭包、五个剧情原始脚本及命令。
- source.inventory.json：完整stage footprint、语义消费者缺口、本地Buff表字节/SHA/所需DB key。

6-16两座hidden frost trap使用精确alias #1/#2、phase0/level1/skill0/level1，
frstar_frosts分支为一个阶段、两条ACTIVATE_PREDEFINED。
6-17三位E2L25原生角色均hidden=true、alias=null、skillIndex=-1。
必须用明确的剧情character-key注册/激活source policy；不能套C5非空alias门，
不能以Python[-1]误选最后技能，也不能静默把slots0与原生角色替换成固定12配置。
五个STORY和三条ACTIVATE_PREDEFINED原始动作保留，尚未建立控制消费者。

## 精确机制依赖

真实FrostNova2两个mode的普通弹道均28帧；复生BB duration10、ATK+.5、
reborn_invincible20、attackfreeze5，IceShield priority2/cooldown35(maxCnt2或3)，
SummonFrosts priority10与branch_id，IceBurst priority1/cooldown10.5/freeze10。
剧情frstar2_s为独立prefab/variant，普通slot NeverTrigger且无OnAttack帧，
不能据名字套普通FrostNova模型；两技能init16/23、cooldown1000，
blood.damage2000绑定PURE NoSourceDamage/ignore SP/without modifier模板。

snwolf/snsbr/snbow/icebrk的1.5/2.5来自BSON e2c_frozen_atkscale：
ON_CALCULATE_DAMAGE先查TARGET FROZEN再改atk_scale，不能作无条件自身ATK增益。
snmage正常20帧，coldattack priority0/spCost2及ReadyEnemySkillEffect要有完整技能消费。
snslime死亡模板先查SOURCE不是SILENCED，再实际发projectile_snslime，BB atkScale2/freeze10。
shield_2普通14帧来源可复用候选仍需精确level/override与消费比较。

寒霜装置sktok_frosts的AnimatedActionToTargetAbility使用preDelay约.8、timeMode2、
loadFromDB e2c_cold；本地buff_table352282.dat整份原始字节与SHA已保留，
e2c_cold literal定位可核验，但FlatBuffer完整schema/字段转换未实现。
Cold→Frozen、属性/控制标志/叠层/时间/资格应从来源明确消费，不用名字推断。

## 来源冲突与状态

trap_010_frosts本地对应token CAB缺失，使用已有官方2025-03-27冻结token AB，
下载证明与SHA保留，明确可替换且未与固定表版本对齐。
本地其他prefab、Spine、BSON、剧情和Buff表均各自冻结SHA；客户端版本对齐待核。
敌人与预定义BSON missing_templates均为空，角色Spine绑定实际提取但未建运行模型。

此目录是source inventory/consumer plan，不是完整stage或client证据。
runtime_authored/formal_approved/whole_stage_executed/client_verified保持false。
