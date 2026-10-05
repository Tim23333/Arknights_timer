# 9-18完整输入组装

固定关卡 `level_main_09-16` 的完整输入包已生成：
`packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v1.life99999.json`。
它包含308个实际可达定义、原始34次出生、25条路线、8槽位与12初始DP，
同一固定12人编队，四个保留原tileKey与黑板的按格场域、三枚预放置柱体和库存2的爆破装置卡。
只有基地生命值改为99999，单位HP、费用、SP、槽位、地图、动作和波次时序保持来源配置。

原生三个柱体的alias均为 `trap_043_dupilr#1`。转换层保存全部原记录和alias，
以 `level_main_09-16/tokenInsts/0..2` 作为实际唯一注册身份，运行alias留空，
没有静默合并柱体或改写来源alias。卡片库存与技能选择逐字段保留，NORMAL1不启用四星/简单模式符文。
hardPredefines的原始空桶容器继续保留在metadata，转换视图中只验证空桶并不实例化。

原生波次、路线预览与符文通过既有严格timeline转换器消费；预定义实例/卡片单独按原始记录精确转换。
波次转换视图不含预定义，来源完整native document未改变且保留digest。
地图、路线、动作标记与所有raw实例在独立输入校验中逐值/逐类型核对。
爆破装置推力参数绑定最终全部Buff定义闭包，包括固定编队追加的Buff，
防止按孤立模块缺省定义误读当前失衡免疫。

输入校验以及62刻真实启动、检查点续跑和公有从头回放已通过，完整状态、任务、RNG、cache/context/value/cause均比较。
小收据见 [input.918.v1.json](../../validation/campaign/chapter09_stage_assembly/input.918.v1.json)。
这仅证明完整源输入编译和启动，不表示后续全部波次已执行。

公开输入计划包含42条实际请求，覆盖12名干员、技能/召唤/卡片尝试及12000刻后的有限撤退：
`scenarios/campaign/chapter09/level_main_09-16/public_plan_v1_finite/commands.json`。
只静态核对地图部署类型、引用和来源配置；实际DP、槽位、SP、控制、死亡及接受/拒绝结果由模拟器生成。
不要求完美胜利，也不把失败请求伪装成成功。

该输入锁定2c38 Duspfr/正HP柱体候选，其自身基线已经完成，完整回归仍在运行。
还需独立源转换/操作计划审核以及完整正向、CP、head、事件观察和出生守恒验收，
之后才能登记本关。所有长/短执行捕获使用E盘固定目录，验证结束保存精简结果后清理。
