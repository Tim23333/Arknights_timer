# 第 1 章场景组装与前缀验证

这是第 1 章两个真实关卡的部分集成输入，不是整关通过收据。主目录仍为 M12，整体模型验收 2/36。
组装采用冻结的 M15 category 候选 `f98a638812a18a01d10505dadd48b01de410ac27e992230881bc01c4f9a993b9`，不修改历史源包或主实现。

## 新输入

`tools/build_chapter01_stage_models.py` 逐项读取实际 native source 文件并检查 SHA，将每个 wave / fragment / action 原始索引、重复数、间隔、延迟、managed / block 标志保存在新的动态 Timeline 中。源路线全部 checkpoint、reachOffset、spawnOffset 和随机范围保留；非零 offset 与消失/重现使用明确的可替换模型规则。根随机种子采用原始关卡值，绑定方式仍是声明模型。

新包位于 `packages/campaign/chapter01_stage_models/level_main_01-11.partial.json` 和 `level_main_01-12.partial.json`。
1-11 保留 45 个敌人出生，1-12 保留 30 个。六类简单攻击与三类高级攻击按定义映射替换，不追加第二套普通攻击；W 使用独立 Boss 定义，场景属性、速度和漏怪值取对应关卡数据库配置。实际 MoveController 的 steeringFactor / maxSteeringForce 进入声明 steering 规则；原生半体宽仍有明确缺口。

NPC 采用独立 E0L20 定义；原始 hidden / aliasNone / 技能配置留存。目前执行的是 activation 时创建的部分模型，原生 dormant 注册、激活前 SP 时钟尚未闭合。固定 12 人来自已冻结的队伍内容，测试探针实体和能力不进入场景。

1-11 的原始 12 张教学干员卡全部保留，固定队伍显式标为测试覆盖配置；`native_training_deck_legal=false`，不宣称该编队属于客户端原生教学编队。1-12 原生卡片为空，但预放置 EMP 存在，真实 native(2,5) 转为 top-origin(5,5)，方向 UP。

## 实际结果

- 1-11 在 f98 候选编译通过，实际闭包 271 个定义。
- 1-12 严格拒绝编译：实际地图含 `tile_telin` / `tile_telout`，当前底座缺少明确的格子机制策略。入口和出口没有删掉或改为普通地面，完整来源与执行缺口仍保留。
- `tools/experiments/chapter01_stage/test_stage_composition.py` 5 项通过（3.43 秒），检查动作/人口/路线守恒、教学编队/NPC 边界、传送格拒绝门及真实开场检查点和回放。初次测试使用错误的 `entity.born` 事件名与错误片段预期，失败报告保留；修正断言后未修改运行实现。
- 1-11 原始场景实际运行至第 805 刻：W 与 NPC 在第 90 刻创建，首个后续敌人在第 780 刻创建；出生敌人 2 + pending 43 = 原始 45。STORY_b 第 630 刻完成并释放输入锁；它阻塞波次、不阻塞片段，下一片段原生 20 秒延迟得到第 690 刻起点。
- 第 95 刻检查点继续至 805 与连续运行相等，从头回放亦相等；共 65107 条事件，全部事件严格比较通过。源文件、实现、builder 和测试身份记录在 `validation/campaign/chapter01_stage_01_11_prefix_20261002.json`。

这些验证只覆盖原始开场，未跑整关胜利，也未代替固定队伍各技能的机制证据。结果没有增加正式进度。

## 仍需推进

M16 地形候选已冻结，待独立复核；投射物候选仍在开发。随后组合新的 runtime 与内容身份，分别补齐 EMP 地形层、W 附着投射物及 invalid 回调、远程敌人追踪与碰撞、原生选择过滤/移动攻击状态机、NPC dormant 激活以及教学编队策略。1-12 传送格将先审计来源，再声明通用执行策略。完成依赖闭包后才固定操作脚本、跑完整关卡、建立独立 source/scope/whole-stage 收据。

传送格来源审计已完成：四格黑板和 effects 均为空，精确 prefab 解析为通用 Tile，没有序列化配对字段；实际八条出生路线含九组隐藏/等待/出现，等待3/35/40秒，入口出口与地图格逐项对应。
见 [传送来源审计](CHAPTER01_PORTAL_SOURCE_AUDIT.md)。新的 M18 候选将声明通用 tile profile，只由原 route checkpoint 驱动，不添加自动寻找出口的行为。该候选开发中，冻结的 f98 部分场景继续保持原字节和编译失败边界。
