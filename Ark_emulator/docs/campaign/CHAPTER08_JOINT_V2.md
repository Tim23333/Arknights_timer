# 第八章通用机制联合候选 V2

2026-10-04：中途数值继续依据用户提供的参考网站、固定游戏表和资源资料核对。
客户端对照由用户在仿真完成后统一反馈。基地生命值为 99999，干员和敌人的 HP、
DP、SP、部署槽位和关卡机制继续使用来源配置。

当前候选在 `unpack_work/campaign_chapter08_joint_v2_candidate`，源码身份为
`a6ca7396556624768da2f83680ae34ad632d36dfa85f646916edbd1ee85f0128`。
它仍是隔离候选；主底座身份和整关计数以 [当前状态](CURRENT_STATUS.md) 为准。

## 实际合并内容

| 通用机制 | 输入契约与行为 | 本次合并来源 |
|---|---|---|
| 动态 Buff 寿命 | 内容指定 `lifetime.rule`、参数和 `count_when_inactive`；按已过去区间的倍率扣除名义时长，历史时间与历史属性使用同一个采样时刻 | lifetime V8 `be1b6be8…` |
| 复活自持 Buff | 真实 `on_begin` 回调生成与实体、Buff、复活代次绑定的内部资格；HP 为零的等待期间可保留声明的自身 Buff；手工刷新、旧代次和伪造标志不能取得资格 | rebirth self V2 `f6fa921f…` |
| 预定义机关重复激活 | 内容显式指定有限激活预算和允许的退场原因；每次复用生成新的实体身份、原始 HP 和 SP，保留旧实体及其在途弹道的来源 | predefined reactivation V2 `08d8a2a3…` |
| 动态计时与复活联合 | 动态 Buff 的非活动清理检查真实自持资格；资格只用于保留 Buff，不授予额外技能或命令权限 | 本联合候选 |

实现保持通用，不按敌人 ID 在内核中分支。敌人、机关、技能、周期伤害、抵抗倍率
和时长仍由内容包、规则和提供器指定。

动态寿命的最小内容配置如下。`rule/custom/buff_rate` 可以是表达式、计算图或提供器；
输入包含来源、目标、Buff 实例、采样时钟及目标有效属性，返回有限且非负的名义时间倍率。
倍率为零时暂停消耗，周期效果继续遵守自身间隔；到期边界不再发出伤害包。

```json
{
  "lifetime": {
    "rule": "rule/custom/buff_rate",
    "parameters": {},
    "count_when_inactive": true
  }
}
```

重复激活配置放在场景的初始实体条目上。需要显式休眠、注册键和有限预算，
避免可变命名别名指向不同实体造成旧事件混用来源。

```json
{
  "definition": "unit/custom/device",
  "active": false,
  "registration_key": "custom_device_1",
  "position": { "row": 1, "col": 1 },
  "reactivation": {
    "max_activations": 3,
    "after_reasons": ["withdrawn", "dead"]
  }
}
```

激活仍通过通用 `activate_predefined` 效果按注册键执行。
首次激活原休眠实体；在允许原因退场后的再次激活创建新实体。
当前实体仍活动、预算用尽、注册记录不一致或回调失败都会拒绝并回滚。

最终源码与 catalog 的逐文件身份见
`validation/campaign/chapter08_joint_v2/final_merge.v1.json`。
早期 `merge.json` 的 `6052fb30…` 是增加真实自持资格检查前的中间身份，不能用于新版验收。

仓库内保存了相对主底座的 11 个精确源文件增量及全部 100 个文件身份，位于
`tools/candidates/chapter08_joint_v2/source_delta` 和同目录 `manifest.json`。
`reconstruct.py` 接收固定基底和新的输出目录，验证基底、增量、全部输出字节及实际导入摘要。
本轮已实际重建验证，输出源码与候选身份相同；该工具不修改主底座。

## 内容与操作输入

新内容通过 `tools/chapter08_joint_v2/build_sources_v1.py` 构建；原实体、技能和弹道字段
与来源内容逐值比较，动态灼烧规则使用新版来源模块。内容身份变化不迁移父版本的通过结果。

| 内容 | 新版路径 | SHA256 |
|---|---|---|
| 灼烧父计时与独立周期伤害 | `boss/dragon_fire.module.v12.joint.json` | `a56cf27ee1c4e1a1a5a63343e90498e0a88120bea5800ed80c834d26cd25d7af` |
| 塔露拉攻击、技能与阶段重启 | `boss/talula.dynamic.v9.joint.json` | `15914279144384efe15cc6c8c69343561df5da3808e06df999794df4cae6143a` |
| 能量聚合体与四向火球 | `flame/module.v3.joint.json` | `297a69559ebed3c062108451b6ede92c08279daea41453b58355145919b20ba1` |

以上路径相对于 `packages/campaign/chapter08_consumers`。

JT8-2 新草案为 `packages/campaign/chapter08_stage_models/level_main_08-16.native_draft.v6.json`，
保留原地图、32 次出生、敌人变体、DP 10 和 9 个部署槽位。
`level_main_08-16.native_draft.v6.life99999.v1.json` 只覆盖基地生命值。
`scenarios/campaign/chapter08/level_main_08-16/public_plan_v4/commands.json`
包含同样的 28 条十二人轮换操作，操作 SHA 为
`f2f73ffd663595c144e98be848d5d820eb5f9a589877c13e20f4320da8f70c24`。
编译、计划十二人和准备操作输入分别记录；实际部署结果须读取执行事件。

## 验证范围

联合候选首次作者语义验证实际执行 60 项、全部通过，源码起止身份相同。
它包含复活、自持 Buff、动态时间边界、时间属性、重复激活和错误输入回滚断言；
报告为 `validation/campaign/chapter08_joint_v2/author_semantics_v1.json`。
作者执行和独立复核分开记录。

联合候选独立复核已最终完成 16 项唯一检查，全部通过；
`validation/campaign/chapter08_joint_independent_v5/freeze.json` 的 SHA 为
`a251750464aecf38394ea0785ce889559a0896c7cbd700e7c0de8171758afb9c`。
动态父候选 be1 的旧完整套件实际为 1218 通过、1 失败：旧测试固定要求 98 个契约，
新动态寿命新增了第 99 个契约。独立逐字段检查确认原 98 项与顶层元数据完全不变。
另建 `run_full_suite_v2.py` 只将该数量断言替换为精确旧集合加新契约及不可变性验证，
其余 1218 项原断言保持不变，完整结果单独保存；旧失败不会改成通过。

候选自己的 0-1 基线已实际通过，包括自定义公式 850／60、真实磁盘检查点恢复与公有重放；
身份收据为 `validation/campaign/chapter08_joint_v2/baseline/verification.identity.json`。
新版灼烧的来源门另外保存了 8 个磁盘检查点、输入和完整事件捕获，
报告为 `validation/campaign/chapter08_joint_v2/source_gate_v1/verification.json`；
源码、内容和辅助工具起止 guard 相同。

新版灼烧 8 项、塔露拉及机关 6 项、JT8-2 输入与前缀 5 项均已实际通过，
各报告的源码起止身份相同，仍属于作者执行。
首次复制的机关测试遗漏 `build` 绑定，产生 1 项夹具失败；修正为真实来源绑定重建后
另存 `author_talula_flame_v2.json`，失败的 v1 报告保持原字节。
正在运行的验证包含候选自身的完整 `tests_v2`、0-1 基线，
以及七个机关分支的 35 次真实激活、140 次火球发射和检查点／公有重放。
机关分支受控场景使用来源位置与原生 25 SP；它的平面测试地图及分支触发时间属于显式测试输入，
不能计为 JT8-3 整关运行或 Boss 触发时序通过。

旧重复激活候选曾在分支验证过程中由 `51ce8f17…` 改成 `08d8a2a3…`，
导致检查点恢复拒绝、起止源码 guard 失败。
`validation/campaign/chapter08_predefined_reactivation_v2/source_branch_v1.json`
保留该失败。新联合候选冻结后重新执行，不能把旧结果改为新版通过。

JT8-3 第二次复活的原生恢复比例为零，终末阶段机制另由独立候选推进：
真实 HP 为零时，在有限期限内执行声明的终末技能和回调，结束后结算一次死亡。
完成该机制的边界验证后再合并，不使用临时 1 HP 或删除阶段来完成整关。

终末机制已合成 [联合 V3](CHAPTER08_TERMINAL_JOINT_V3.md)，但独立复核又发现
普通嵌套 Buff 回调可借外层结束资格的真实缺陷，修复版本继续推进。
机关模块 v3 的原始 `consider_unhurtable=false` 参数遗漏也由新内容 v4 修复，
旧源模块与反例保持原身份。

独立机制、完整过程、来源数值核对和用户实机反馈沿用
[参考优先验收契约](REFERENCE_FIRST_ACCEPTANCE.md) 分别记账。
