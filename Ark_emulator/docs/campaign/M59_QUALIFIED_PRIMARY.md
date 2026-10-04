# M59：合法捕获主目标与格区域并集

新候选 `../unpack_work/campaign_m59_area_primary_candidate` 从冻结 M54 复制，唯一 core 改动为 `domains/qualified_areas.py`。实现指纹 `84b4146bd574dda5dfd833314bee46c4370e583bcc8ef900075911fdafadbd9a`；原 M53、M54、M56、primary 与旧内容没有修改。本候选复用既有 `area.members`、`targeting.eligibility`，没有新增合同或默认绑定。

`ark.area.qualified_cell_offsets` 新增可选 bool 参数 `include_primary`。缺省或 False 时保持原几何逻辑。True 要求实际纯上下文含 captured `ctx.target` entity snapshot，不能由 source 或内容 literal ID 猜测主目标。区域是格偏移成员与捕获主目标的并集，但主目标必须先出现在 EffectSystem 的候选池：真实 active、alive、selectable、route-visible，并通过已绑定的 `targeting.availability`。随后和格成员一样调用配置的纯 `targeting.eligibility`，因此不能绕过 target-free、side、motion、category、camouflage 等资格；9 是 actor-bound availability 的明示数据策略，不是内核固定数字分支。各 actor 只迭代一次，主目标同时位于格区域时不重复。

`candidate_final.json` 位于 `validation/campaign/m59_area_primary`，SHA `09f9d50a164bc0eadf640c42167ebd492a9d215550f102af3d57c0ee361db5f8`。25项 fresh 独立实际测试3.90秒：格外主目标、缺省与False、并集去重、5种资格负例、captured target后续死亡/free、route-hidden、显式9与实时immune9、免疫到期同帧拒绝、必须有primary context、编译strict bool、真实规则失败整体CP恢复、到期projectile一次命中、公开 ordered CP/resume/commands replay，以及新 Mortar source 内容的真实 moving/live ATK 和格外到期350。源10秒 lifetime在压力夹具中显式替换为 .1秒，以验证边界，不把 .1秒称为原生参数。

父 M54 与 M59 分别在独立进程执行同一缺省 `include_primary` 内容与 seed，snapshot、World、resources、scheduler、RNG 与全部事件逐值比较。报告仅分列实际根 program/runtime 身份、规范 calculation trace 的 registry runtime 身份，以及新改动提供器自身的 rule fingerprint/source SHA；后两项限定在 `ark.area.qualified_cell_offsets` trace，未泛删同名字段。inputs、parameters、context、计算值、包数和状态全相等。第一次严格比较遇到该已改动函数对应 rule fingerprint，诊断日志保留，修正身份分类后完整复跑25项与公开CP，不宣称 raw bytes 跨版本相等。

新内容 `packages/campaign/chapter03_models/mortar.primary.reference.json` SHA `632e455ac41ee3b2d95cd3d8d53fb8a6205445406d69df92b3f627763d3e7163`，由 `tools/build_chapter03_mortar_primary.py` 生成并实际 `--check`。它独立继承冻结 `mortar.targeting.reference.json`（3d205d2d…）与原 7b7e9e45…；两个旧包不修改。原始 Simple `_alwaysHitTraceTargetInTheEnd=1`、Hit ignoreTargetFree0 与 [PRTS 炮手](https://prts.wiki/w/%E7%82%AE%E6%89%8B) 的强制主目标说明，现在有 include-primary 的实际数学消费者：到期局部点以外的合法主目标被纳入，同时不赋予任意邻近 crate4 权限。M59 本身是 M54 父，没有 M55/M57 route_obstacle schema；原 source crate 的接触、摧毁与继续路线必须在 Root 下一组合身份再验证，旧 M56 source crate证据不迁移。

M56 上此前 reference-targeting包完整冻结 SHA `3d205d2d3c673d63b2380073c2bbf1db292d1f3bf11321a27104033f8575c8fe`；5项8.66秒和native crate CP35→205/resume/replay报告 `eda6691749ac50fb77fada4a1f60a1f55cc259413b74424b770cc0fce15b3f06`。它真实public deploy/source category4→route contact→source f16单壳，raw physical400对HP100crate实际消耗100，飞行邻居350，之后terrain清除、敌人继续路线漏1、基地99998、stock4。邻近第二crate4首blast时仍HP100；普通已阻挡目标资格优先，不被taunt20抢走，free blocker没有fallback。原 raw `_combat`/`_attack` 同PPtr与 FROM_OWNER1、普通cat1/range7仍保留。最初夹具在形成阻挡前已开始旧cast、以及把raw400误当HP实际损失，已保日志并修正测试契约，非core缺陷。

PRTS参考索敌与障碍规则、源数据、声明算法三者分列。native Paracurve三维、buildable特殊处理、callback顺序、原生方法正文仍待用户反馈；整数base taunt计分可替换，对任意 fractional/live-modified taunt不宣称等价。M56已知 stale obstacle callback缺陷没有因这些源crate无额外callback的案例被批准，本M59也未包含其修复。client_verified=False，未跑整关，未签formal或整关收据。
