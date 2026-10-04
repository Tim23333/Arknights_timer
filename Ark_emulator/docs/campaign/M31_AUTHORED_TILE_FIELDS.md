# M31 通用显式地板Buff场

新候选 `unpack_work/campaign_m31_tile_field_candidate` 从冻结M27/75fd构造，当前core `7720452f53f4e8b1e0c3e2ba77ab03e0b0b8e8e3b2cdfabf79fe9499f967e96d`。旧primary/M27/M29/正在执行的关卡均保持字节。

地图作者可以把任意自定义tileKey绑定到 `map.tile_mechanics` 中的 `occupancy_buff_field`，字段为type、definition、expected_blackboard。definition是显式静态 `tile_field_owner` 实体，必须含初始parent aura，不能携带combat/deploy/ownership/terrainoverlay角色。每个对应地图格生成独立owner，实际成员由已有选择器、资格和parent-owned Buff接口决定，可替换公式与范围保留。

Blackboard所有键和值需逐项匹配显式契约，未知、重复、字符串型或未绑定值拒绝；非空effects仍拒绝。Expected board是数据，不被误读为rule/provider/definition引用。该契约锁作者声明的数据，没有宣称未知原生LoadData或getter算法已经恢复。

所有定义/Buff/selector/rule真实进入Compiler闭包并核对kind；未知map key无profile仍拒绝。Field owners属于内部模型表示，tags不允许enemy/player/roster，不是公开干员、敌人或目标人口。普通/纯目标查询、area及effect-target可用性均排除它们；source仍active，可承担Buff所有权。每格owner与来源tile/BB记录在World `state.tile_fields`，CP/事务状态由既有World管理。

门户profile保持独立：配对检查仅识别route_checkpoint_portal，不把普通Buff场当传送入口/出口。地图必须显式row-major tiles；没有opt-in的旧输入不创建字段、不写新state。

实际10项新检查与28既有spatial/scenario/aura检查共38通过7.49秒，包含任意tileKey、公开进出后HP500→530与child清理、实际存盘有序CP/回放、两格独立parent、sourceBB负例、错kind/敌人owner拒绝、reference-like BB键及内部owner隔离。原M27与新M31在相同完整1-12源场景30刻427全部events、World/RNG/scheduler/state/program逐值相等，runtime身份单列；这不是全程证明。完整0-1基线30744与独立peer正在运行。

M31只提供通用声明机制，不把现有格投影/虚拟owner/独立child stacking当原生BuffTile回调。第2章仍需source数据到profile/HPdriver的明确转换、实际目标资格、原生覆盖/堆叠、精度/同帧顺序、动态TileMode以及HoleTile接口；实际游戏准确性pending。诊断ledger要新增field owner分组，不能将它当wave/预定义人口。

源码patch、输入与测试见 `validation/campaign/m31_tile_fields/`。作者能够便捷自定义实体、Buff、选择器和公式，此批不引入官方tile ID的内核分支。

更新：完整0-1基线30744已真实exit0，11/0、181937全部事件，内存CP/完整命令回放及custom850/60通过，core/source/hash前后相等；独立peer继续。字段owner账本单列实际1内部field、0wave/registered/owned，读取前后CP相等，不污染关卡人口。

独立peer随后发现静态路线与effective instance覆盖旁路，旧M31源码和绿色证据不改且不提升静态完整性；新M32/M34分别修基准空间驱动和实际覆盖/创建/Ability入口，详见 [静态实例修复](M34_EFFECTIVE_STATIC_FIELDS.md)。
