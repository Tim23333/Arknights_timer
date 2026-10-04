# 第八章终末机制联合候选 V3

本候选将动态 Buff、自持复活 Buff、有限机关复用与真实零 HP 终末阶段合并。
源码身份为 `5cf7c70f61d20585b795417db423b9bf2914c1ad06c251730331d639b2252b23`，
由联合 V2 `a6ca…` 加终末 V3 `ebc5…` 的五个精确文件增量形成。
父候选保持原字节。本候选仍存在下述已确认的回调授权缺陷，不能推广为主底座。

后续修复已经形成 [联合 V4](CHAPTER08_TERMINAL_JOINT_V4.md)，保留本版本作为失败历史。

## 已实现及实际验证

终末机制由实体的 `rebirth.zero_restore_lifecycle` 显式声明，限定适用的复活次数、
有限持续时长、内部技能、保留 Buff、进入效果和结束 Buff。
只有真实复活恢复计算得到零时才进入终末状态，HP 保持零；
普通攻击与公有技能请求不能借终末状态获得执行资格。
声明的结束 Buff 在正常到期回调中使用原生 `skip_rebirth=false` 的死亡请求，
截止任务先按正常流程移除已到期的结束 Buff，仍未结束才走明确的截止结算。

实际作者语义验证 61 项全部通过，包含原有联合 60 项及精确 catalog 扩展检查。
真实来源场景完成第二次恢复比例为零、28 秒终末阶段、30 次 693 法伤、一次结束和死亡、
磁盘 CP400 续跑与从头重放比较。

晚于死亡的三颗在途火球也已实际验证：来源 Buff 在死亡时清理，弹道的
`source_attributes=at_hit` 在命中时读取 ATK770，RES40 下各造成 462 法伤，
CP1145 续跑与重放相等。
首次复制的测试仍期待 693，失败报告保留；新测试同时检查命中时来源 ATK770，
没有改为保留已死亡来源的增益。

自己的完整回归和 0-1 基线仍在运行。主底座及完整关卡进度以
[当前状态](CURRENT_STATUS.md) 为准。

## 独立发现的回调授权缺陷

独立复核在终末父候选 `ebc5…` 上执行了真实反例，本联合候选继承相同实现：

1. 第二次零恢复在 tick4 进入，终末截止为 tick14。
2. 声明的 completion Buff 在 tick10 到期，其回调只移除普通 OTHER Buff。
3. OTHER 的 `on_remove` 请求 `InstantKill skip_rebirth=false`。
4. 当前实现搜索外层授权栈，OTHER 借外层 completion 资格，实际 tick10 结束。
5. 原预期为 tick14 截止结束；OTHER 自身没有结束终末阶段的资格。

报告 `validation/campaign/chapter08_terminal_independent_v2/verification.json`
的 SHA 为
`bcd560882e5d1499a51a95bb174cbcef1b61c7bc69cf5d4e0bfb2bfc88640801`。
原期望、完整输入、真实检查点、回放和源码 guard 保留。
修复会另建终末 V4，限定当前回调身份，未授权的嵌套回调必须遮蔽外层资格。
修复后继续验证返回外层时的合法结算及故障回滚。

## 完整 Boss 仍需的内容

精确依赖矩阵已写入
`packages/campaign/chapter08_consumers/bsnake/requirements.v2.json`，
SHA 为 `227a6ac5fc0d581a8c5e90241d05a24b26c4cf4bf8ed67b14dc9a505234d9dd2`。
它保存四个模式、十一套 Buff 模板、来源技能黑板和九项消费者要求。
正常攻击、来自灼烧者的减伤、首次火雨及 15 秒无敌、点燃、爆炸再点燃、
机关预告与分支触发、波次控制都须逐项实现并独立验证，不能用终末局部场景代表整个 Boss。

## 源码复现

`tools/candidates/chapter08_joint_v3/manifest.json` 保存五个增量及全部 101 个源码／catalog 文件身份。
同目录 `reconstruct.py` 已实际重建出一致的候选身份。
该目录保存已知缺陷版本作为可复核的历史，后续修复使用新版本。
