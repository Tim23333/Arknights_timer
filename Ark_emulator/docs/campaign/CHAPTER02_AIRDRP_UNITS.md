# 2-9两种空降地面单位源绑定与出生模型

固定源包SHA97447895...0d492、attacks.model SHA92ee425d...e0d0。生成器只消费2-9的resolved_variant_ids实际两variant，不按名字猜动作；重新用pinnedDB解析native_reference、核level0/overwrittenData null及variant digest。读取实际root/mode/combat/MoveController所有Unity TT，Spine映射f13与旧冻结attack子集逐项相同。

| variant | HP | ATK | DEF | MRES | motion | mass | block volume | speed / baseAT |
|---|---:|---:|---:|---:|---|---:|---:|---|
| enemy_1013_airdrp@0/20e3225f73e1c6e6 |1450|220|100|0|WALK|0|1|1 / 1.9s|
| enemy_1013_airdrp_2@0/8903647724c13db5 |2300|300|150|0|WALK|0|1|1 / 1.9s|

massLevel0是defined true的真实零，不作fallback。Enemy._blockVolume1绑定block_cost；enemy block_count0是显式容量模型默认，不把DB未defined blockCnt0假称源值。HP、ATK、DEF、MRES都取对应variant，不改变生命或伤害凑通关。

唯一mode的_combat指实际MeleeAttack，_attack与_attackTrigger为NULL；INPUT_TARGET2按当前声明blocked-target接口绑定。Owned ability/selector与新decision真实进入Compiler闭包。MoveController8/10绑定可替换bounded steering，arrival .05为模型参数；原halfBodyWidth0.20000000298和native分离/物理/body callback单列后续用户反馈。

## 冻结post-born层

新airdrp.post_born.partial.json SHA `5ffcd1847eb87eba8830b5001a6fd6b386946f55eafd0c4e65684575c9e60f4b`，不改chapter02_sources/first7/projectiles7。9项fresh7.11秒，4实际fixture、源/helper/currentM37 c77前后锁与实际input byte SHA，CP/replay相等。真实Spatial建立blocker关系，first combat starts1，f13→tick14，next interval57→tick71，实伤分别120/200；unblocked移动而不找其他普通近战目标。错stage/level/overwritten、技能/talent注入均拒绝复用同名variant。

报告post_born_final.json SHA `4ece624b89380faac83cf5489b71b903c6656070d6ec91fe26427ba7754a439d`。这层旧的complete/native reject明确因为出生尚未消费，不作为最新用户“仿真后统一对照”的client-body门；当前交付使用下面新birth模型。

## 显式45tick出生模型

两root _delayToBorn=1.5，_onlyDelayToBornOnTileStart=0。新airdrp.birth.model.json SHA `8bbe5f24351458257886c14e1a5f0994660d8d879897395383d6cec4fea8d602`，源实体在实际wave SPAWN时创建，初始Buff从创建起暂停move/attack/abilities，区间[created,created+45ticks)，不是stage开始登记全部未来敌人。

Targetability、visibility、block关系写明策略。当前交付是targetable/visible、birth block_cost0暂可配置；并不改变实际HP，也不添加无源免疫。cost0表示不占blocker容量，关系仍可能被建立；native关系时点后续用户核对。可选target_free_eligibility通过Buff.selection_flags投影，已有资格选择器见证，不把未接eligibility的玩家选择器说成也受控。

6项fresh8.33秒/5实际fixture，reportbirth_final.json SHA `13b22aef1c786bd1bc86ebadcf908119dc87d8533d407046dbb652ac0b4ea090`。45前不移动、不cast、HP保持1450/2300；45半开恢复并发enemy.birth_phase_finished；真实path/block建立后46开始cast，f13→59伤120/200。调度完整CP/recorded-command replay相等。44手动probe被controls拒绝，45可接受；源block occupancy计算trace从0恢复真实1，未用会发日志的ctx属性查询污染回放。

两个build/check通过，Runtime只读M37，未新增内核官方ID分支。当前模型可按明确参考/固定源表策略进入仿真交付，clientverified仍false，动画缩放、born目标资格/Block反馈和nativegetter待用户统一核对。

## 2-9五variant合并接口

Stage builder应按resolved_variant_ids构造唯一映射，不能按name选择任意level：

- yokai@0/94e6...：first7的unit/chapter02/enemy_1005_yokai，FLY/Empty combat；没有攻击fallback。
- yokai_2@0/dbec...：first7的unit/chapter02/enemy_1005_yokai_2，FLY但实际f8 physical/radius2普通攻击。
- defdrn@0/46bb...：first7的unit/chapter02/enemy_1017_defdrn，FLY/DEF300声明BB圆2.5 Aura，exclude self。
- airdrp@0/20e3225f73e1c6e6：新unit/chapter02/enemy_1013_airdrp/level_0/20e3225f73e1c6e6，WALK/f13。
- airdrp_2@0/8903647724c13db5：新unit/chapter02/enemy_1013_airdrp_2/level_0/8903647724c13db5，WALK/f13。

合并时source/definition重复必须逐definition等值才允许去重。只取birth模型的两airdrp entity/ability/selector/behavior/steering/birth Buff闭包，另外三种仍取冻结first7；Root地图/波次层保原52spawn、Info7、managed flags、实际route motion与offset。三flyer source born delay0，两个WALK delay1.5，不泛化所有敌人一律等待45tick。新创建与旧非wave token/NPC/virtual field owners分别ledger。

机器可读合并设计为main_02-09.enemy_binding.plan.json SHA `346a6bfc20add835d70d65ea18b09310d8542578be0693a8228891a7cbcebd9d`，build/check通过：五variant各26/8/2/12/4共52，明确package/UID/原始reference、可从源补的mass/block字段及是否有未defined质量。defdrn的massLevel并未在resolved表定义，不能默认把它称为源零；如果force profile消费质量，需按当前参考模型声明默认并保留反馈字段。该JSON是join方案，不是整关执行输入。

当前还需Root地图推进tile_hole真实移除/坠落语义（不作noop或road），gazebo只对FLY目标的1.7伤害与AS−20、其他tile BB完整消费；defdrn SilenceableTalent开关和parent Aura暂停/恢复需要明确状态driver，单纯abilities控制不自动关闭初始Aura。source圈1 vsBB2.5取明确参考BB圆模型，axes/physics留反馈，不因clientbody缺失阻断当前声明仿真交付。整关脚本/模型数据仍要完整实际运行，不能把这些微场景叫整关已完成。
