# 第5章整关组装与当前证据

2026-10-04 当前组合v3 core8fa4e367...已完成1219项完整回归、0-1基线、自定义公式和独立源机制复核，Root推广为主底座（promotion SHA `dacc0a413c6b966017bff9339189de4fb71056388aab3a6c9f9072273f206c44`）。5-9正在执行固定12原始整关，所有12首次部署已受理；5-10输入及900帧真实CP／公开重放已准备，等待5-9原始执行自然终结再启动。完整过程／磁盘CP／从头重放收据仍5/36，正式registry暂4份；第5章尚未据此提升计数。以下旧矩阵、失败和执行快照保留各自身份，最新输入为combined_v3目录，不将旧证明迁移到新核。

源计划固定提交 `56aee3d6c5a29c3a0d192456d70d14252cbb0804`，计划SHA `c33c5a199fce73ef7b7524e0d29e59eeca6eb69a7f2ebd7d8c253634b050bee6`。

| 关卡 | 原始出生 | 精确变体 | 原部署上限 | 原初始DP |
|---|---:|---:|---:|---:|
| 5-9 | 51 | 4 | 8 | 10 |
| 5-10 | 73 | 6 | 9 | 0 |

两关共8个精确变体，不能把跨关数量误写为单关8个。原生命值3、费用上限99、移动倍率0.5及原seed保留；基地99999使用独立标准覆盖，不改单位HP或技能。

`tools/chapter05/build_stage.py` 已实现严格引用入口：所有variant逐一匹配模块中的native_variant或完整唯一native_reference；compose模块冲突直接拒绝；ballista实际预定义profile与5-10全部10注册key必需；原7phase分支必须完整同源之后转换IR；原地图、路线、rune、预定义和控制动作由既有严格转换器消费。源parent保持life3，不生成缺依赖的“部分整关通过”。

实际敌人组合矩阵 `validation/campaign/chapter05_join/enemy_matrix.json` SHA `4423a06e4faf07fa35be7c48d7e7d8b3b5631e422ebfdab8cd610b99f8f47991` 已核对243定义无冲突、两关全部精确variant对应消费者。这个矩阵只证明定义组合和绑定，完整stage尚待ballista消费者及独立审核。

普通lunsbr／wteeth原模块dda894f3...已补作者执行与Root独立4项验证，独立报告76c639ea...：实际ATK350／500对DEF31物伤319／469，相对cast命中12／19帧，间隔60／90；受80真伤后不回血、withdraw后失去阻挡／停止伤害、死亡只一次生命周期，真实CP／从头回放一致。初始独立夹具缺ATK及误用amount，被真实伤害管道拒绝，旧失败231dc24d...保留；新夹具补实际属性／scale，未改变硬数值期待或模块。

regen两变体已有34作者／17独立通过；special hammer／lunmag3作者通过、独立排队；Mephi45作者通过、独立排队；Faust三技能35组合／4独立通过，候选完整suite和基线运行；ballista固定朝向ray／qualified swept collision及实际SP／地形／休眠消费者正在独立候选开发。所有这些需组合后再次核对，随后才安排固定12整关与完整检查点／重放。

当前持续目标仍36关，正式完整过程／确定性计数4/36。第5章source矩阵或单机制测试不能提升整关计数，客户端核对由用户后续统一反馈。

近战法师旧cbc8模块的未阻挡远程触发缺陷已经独立发现，新special模块a491491f...修触发行为，原矩阵保旧身份；新 `enemy_matrix_ranged_guard.json` SHA `4782e5550b01ac17d78337c2ee3be0fc86d4fa3ea67e56594f37d387dcdcb7ca` 实际再次核对243定义和全部变体。关卡入口已切换到正确sourcepin，不用旧坏模块继续组装。

5-10原始十个hidden弩炮还需要明确的休眠转换。新增converterv3 SHA `85017cfda3a47c707ee16e7608afdda711333a68a32d2c8e9c2c5ddb316a8386` 保v2其他所有转换门，只接受active严格False、registration与instanceAlias均等于原alias的hidden实例；可见实例不得变成休眠。6项source转换／负例实际通过，旧v2保持原字节，完整弩炮运行证明另由模块完成。

后续独立输入反例发现v3未严格原始hidden数据类型／全局alias唯一性，旧5fail不改；converterv4 SHA `4882dba0a90712a84849d5068f2789c04b6fc213a0ecbd9b80a130f264153176` 补这两门，24独立fresh通过51d0d24d...。C5join固定v4不篡改原source hiddenTrue。

近战法师还存在首次cast比阻挡结算更早的目标错误，新contentfa314fcf...启用通用捕获前settle。入口固定此新pin；最新敌人矩阵 `enemy_matrix_selection_settle.json` SHA `acf5736cb1f0bcafce3868130bd0798072512794e0592cce388e0ad795acb4dc` 实际再核全部243定义，原cbc8／a491矩阵保历史。完整runtime将使用含settle的新组合核，当前不能用旧核心编译新字段。

## 实际组合闭包与机制链

球弩v2源码消费者1860c048...已167作者／兼容通过，Root6独立新场景通过，ray49af三文件及无特性比较归档d030a6d6...。首次接入combined146时，两关native-life3完整Compiler引用闭包均实际通过，标准99999单独覆盖也通过。

随后独立settle反例发现同步回调嵌套技能时旧runtime覆盖内层cast；6350e435...修后重读actual runtime及控制／技能持有／条件／冷却／占用／编号，原15期望全部通过，独立fresh3补18通过c078574d...。当前组合v3 core `8fa4e36752e92f7de691f0e617adb0b3fdb0188f1f4e17c519514b7f51a7e525` 保全部branch、status、settle与ray能力；两源关Compiler再构建通过：native5-9 SHA `3a4c0e81a894f0ec47cb365dd7ab2862eb636cf909470d8f9b399ef7f45545c6`、native5-10 SHA `f33a6951a0bf30fed1ca8ce76c25c7ad7854bf0bef36d0b1220c1e69b245fd53`，标准overlay `c7d18db359f1fbe01bec0073f8e08761d75ae8266a1b4588ba141adc235a7b93`／`abe3e47ca0cc6892ddf0e99cdd3c2b93ec7b247d92137fb5fbc5ab60066f9844`。旧146输入与证明保持原身份。

真正源装置机制链已在最新8fa实际完成：Faust初始450释放／477激活第一个原始弩炮实例，其自然SP达到5后真实扣5并发射，命中DEF100目标实际500；其余九个实例仍dormant、World仍同十装置，没有用dummy或额外spawn替代。476真实检查点固定repo路径保存、按SHA载入续跑和从头回放全值一致；输入／事件／快照／重放／CPpin收据 `source_chain_disk_v3.json` SHA `a94a4a3b42cdb743f280751dd6a3a06f27fd4d05366c8e270e6e0f6d48d8e9aa`。

这仍是受控组合机制证据。最新核的完整suite／原整关短前缀及独立组合复核正在进行，两关完整全程尚未开始验收；不能把单链证明写成73次完整出生通过。
