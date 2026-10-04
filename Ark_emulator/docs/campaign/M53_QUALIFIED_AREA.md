# M53：投射物落点的显式资格消费

候选根为 `../unpack_work/campaign_m53_qualified_area_candidate`，父版本为冻结的 M48 `a829685336bc55af4d5b3098f6eca9887ce870906ab20429ec43de789630fbc9`。M53 实现指纹为 `5ed2a57028755f6781bccfbc6845ad62fd841f5d96d55f1d49cdc973acace047`；所有旧候选与 primary 均未修改。

新增纯提供器 `ark.area.qualified_cell_offsets`，复用 `area.members` 合同。内容必须显式给出整数格偏移和 `eligibility`（纯 `targeting.eligibility` 规则、完整 typed defaults、原始选敌配置、相对阵营与 neutral 策略）。编译门检查配置与规则合同，运行时再次验证。提供器通过 ProviderContext 的纯 calculate 调用资格规则，子调用保留在实际 `area.members` calculation trace 中。提供器只读取传入快照，不读取 World、不排序、不抽随机数、不缓存跨 tick 状态。

EffectSystem 在此提供器启用时，才向纯上下文投影源与候选的 `selection_state`。投影复用既有半开 Buff 状态并集：到期 tick 已不贡献 target-free、ally-free、camouflage 等标记。源身份、职业、运动、类别与默认策略独立保留。格投影仍是已有 `floor(position + .5)`；重复偏移通过格集合去重。源配置只许可 camouflage 17 时，不能解释成 INVISIBLE 9 的许可。M53 的 M48 父没有 M49 的 `targeting.availability`，所以 9 的实时可见性消费者必须在后续合并版本绑定与执行，本报告没有宣称单独完成它。

`validation/campaign/m53_qualified_area/candidate_final.json` 锁实际模块路径、起止指纹、四个改动文件、20 个实际测试及所有编译输入字节；SHA 为 `1542a1e852b28cab2bea31589903319b0325e216722d2003ebdae450ce655c52`。20 项 fresh 测试耗时 1.94 秒，覆盖源资格、飞行、迷彩许可、禁选、同阵营 ally-free、无效 inactive 枚举不穿透、启用未知枚举拒绝、错误合同、替换规则实际消费、严格决策输出、真实规则失败整体原子恢复、公开命令与 ordered CP/replay。最初扩展测试误读 checkpoint 的 rng 字段所造成的夹具失败保留日志，已修为真实 RandomStreams snapshot 比较。

`noopt_parent.json` 与 `noopt_candidate.json` 由两个独立进程分别加载 M48/M53，同一 radius 内容及 seed。snapshot 和 checkpoint 全部字段逐项比较；唯一排除是两处根 `runtime_fingerprint`（snapshot、checkpoint各一处），program 指纹未排除，World、调度、随机数和完整事件全部比较。旧 radius 分支未新增状态投影或 calculation。`compat_fresh.log` 另有 81 项既有 domain rules、activation controls、abilities 测试全部通过，4.69 秒。最初兼容命令拼错旧测试文件名，未执行测试；该日志保留且不计成功数量。

这是一条真实可执行且可替换的数学资格接口。原生 ValidateTarget、碰撞与阵营映射方法正文尚未恢复，后续用户统一实机反馈单列；本报告不签整关收据或客户端准确性。
