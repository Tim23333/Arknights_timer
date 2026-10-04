# 第2章地板来源与数值子依赖

Root实际读取 `[uc]tiles` CAB、三个root GameObject及MonoScript、BSON模板和当前dump，生成 `packages/campaign/chapter02_tiles/source.reference.json`，SHA `fc5ea7050014f56b5725be44805c9c81d17e157615a7eeb7c5d64401059610af`，锁7份来源。地图位置保留native row/tileindex，未猜测连续身体接触或row翻转。

来源事实：

- `tile_healing` 是BuffTile，属性19（HP_RECOVERY_PER_SEC_BY_MAX_HP_RATIO）从关卡BB取.03，infinite life2，clearBuffsWhenLeft1。
- `tile_gazebo` 是BuffTile，属性7（ATTACK_SPEED）从BB取−20；BSON `airforce_enhance` 在ON_CALCULATE_DAMAGE先IfTarget FLY_ONLY，再AtkScaleUp读取atk_scale1.7。因此不是所有目标统一ATK1.7。
- 两BuffTile TargetOptions均side1/motion3/category1/advanced0/sourceSide1；未启用的高级字段保留，不把其零值转为active过滤。
- `tile_hole` 是HoleTile，无Buff数据。当前dump仅声明OnEnemyEnter/OnEnemyMotionModeChanged，方法体为空，不能据此证明原生致死/运动代价。

`buffs.partial.json` SHA `0101470fa4e3d9426f9e5b10a2f62033b80dfbcf9f9c6458da68ba800b02a697` 只实现数值子依赖：恢复比率attribute+.03与可替换resource.recovery；显式攻速比率−.2；飞行目标的damage.request图scale1.7。没有改V2核心，没有假装BuffTile进入/离开/资格driver已实现。

四项实际测试通过（3.46秒）：公开施加/移除Buff后HP500→530，离开后停止；有效maxHP2000时每1/30秒回复2并钳制上限2000；地板攻击地面/飞行/移除后飞行实际伤害90/160/90；攻速比率1→.8→1。两个实际fixture与公开命令完整CP/replay相等，source/helper/core前后SHA稳定。

最初damage.request使用expression被既有catalog正确拒绝，保原2失败report；改为合同支持的graph后通过，未放宽catalog。源builder/check与Buffbuilder/check均实际通过。证据 `validation/campaign/chapter02_tiles/source_operands_final.json` 和 `tests_final.json`。

完整stage还缺通用地板occupancy/enter/leave、目标侧别与异常资格、恢复精度/时序、原生hook顺序、坑洞进入/飞行/运动模式改变接口。对这些保持pending与完整拒绝，不以本数值probe批准2-9/2-10或客户端准确性。

## 声明格子成员模型

另外两项probe复用现有V2 grid_offsets单格选择和parent-owned aura，未改核心：公开move进入/离开后HP500→530、退出后child Buff清理；单位公开退场后恢复停在503且field成员表清空。两项完整CP/commands replay相等，证明通用格子/成员接口可复用。
这个adapter使用显式virtual field owner和每owner独立child；与原生Buff maxStackCnt1/覆盖优先级并不等同，metadata单列差异。半格projection是现有数学profile；尚未绑定native BuffTile接触与source/target getter，不提升原生准确性。初始fixtures用了错误initial Buff结构、错误region标签和不符合aura合同的refresh成员，三份拒绝报告保留；按现有schema改为字符串ID/grid_offsets/明确独立成员adapter后通过，未放宽任何validator。

## 类型化运动状态适配

新 `buffs.motion_state.partial.json` SHA `25d8b684b3ed96f4274feeaab65a455db07550ab5f06575cdf7b972f19b62c10` 使用明确 `selection_state.motion` 的FLY位，而非字符串标签判断飞行目标。第2章源模型用fly标签，早期probe用flying；这两个名称不能承担来源语义。两独立场景通过：actual fly标签/motion2实际160伤害，ground/motion1为90；仅flying标签而motion1仍90。HP/攻击/1.7值不改，CP/replay相等。旧010147包／证据保持。

当前参考优先交付允许对未知callback/覆盖时序给出明确可配置模型，用户之后核对；这些实现不能空处理或错误消费源字段。
