# 第八章终末机制联合候选 V4

本候选修复 [联合 V3](CHAPTER08_TERMINAL_JOINT_V3.md) 的嵌套 Buff 回调借权问题。
当前源码为 `20e8126120668fece832e8b6e23fd53a68fb013656a4476b5ad8e53850f6dd30`，
在 V3 上只替换 `domains/terminal_lifecycle.py`。
全部 101 个源码和 catalog 文件固定在
`validation/campaign/chapter08_joint_v4/merge.v1.json`，候选仍隔离验证。

后续门已完成：自己的1219项完整回归实际通过2337.66秒，源码起止稳定，报告SHA
`37e385c2f861209e56653aa8f172eaebf2e9223c233cf8a59ca4757f7afcbe4b`。
与基线、独立25项收据共同核验后，已精确推广至主底座；101文件逐字节相同，
推广收据为 `validation/campaign/chapter08_joint_v4_primary/promotion.json`，SHA
`2a7df8e6a3f8cad2e5e187d47e43e0e5748923fbaae17afa0fb172ebbff5137b`。
下面隔离运行的状态描述保留当时历史，完整Boss与整关仍未随推广自动通过。

## 当前回调资格

所有 Buff 的 `on_remove` 回调均压入自己的来源、目标、实例 UID、代次和授权状态，
包括没有终末结束资格的普通 Buff。结束请求只检查栈顶当前回调和已签发的真实资格，
未授权的嵌套回调遮蔽外层资格；返回外层后可以继续合法的原回调。
离开作用域时使用 `finally` 清理，事务故障恢复 World、事件与随机状态。

原反例在第二次零恢复 tick4 进入后，completion 到期 tick10 只移除 OTHER。
OTHER 的死亡请求现在不能借外层资格；终末阶段按预期在 tick14 截止结束。
真正 completion 的原生 `skip_rebirth=false` 请求仍在 tick10 正常结束。
这两个原期望均保持不变。

## 实际验证与在途门

本候选作者验证已实际执行 66 项，全部通过：
原借权复核的 5 项，加联合语义与精确 catalog 检查的 61 项。
源码起止身份相等。报告见
`validation/campaign/chapter08_joint_v4/author_core_and_original_counter_v1.json`。
独立复核正在本候选上实际重跑 9 项终末边界与 16 项联合机制，分别冻结。
终末来源两项已实际通过，225.33 秒，源码起止身份相同：
原生零恢复、28 秒火雨、30 次 693 法伤与一次死亡，以及退休后按命中时 ATK770
结算的三颗 462 法伤弹道，均完成真实磁盘检查点和从头重放比较。
报告为 `validation/campaign/chapter08_joint_v4/author_terminal_source_v1.json`。
自身完整回归和 0-1 基线仍在执行。

0-1 基线后续已实际完成，身份收据 SHA
`b470b1346c70521b0260f7bcbc3c197cae00b04c5a329d6bd66708a272f842e8`，
源码起止相同。独立25项已全部通过，冻结收据 SHA
`726e3aa067c8d994cb7f052074cc0e956ecf8043f53edfbd73015e602c76cefe`。
完整回归仍需读取最终结果后才确认。

完整回归使用 `tools/chapter08_joint_v2/run_full_suite_v2.py`。
其唯一更新是将旧“98 契约”断言换为逐字段验证旧 98 项加新增寿命契约及不可变性；
其余 1218 项原断言保持不变。旧套件的数量失败结果仍保留。

机关内容修复版 `flame/module.v4.joint.json` 的四条射线显式传入原生
`consider_unhurtable=false`。Root 在本候选上新增独立目标抗性 17／37／53／73，
命中后普通倍率 .75 得到 622.5／472.5／352.5／202.5；
将同一参数改为 true 的对照场景被对应资格钩子拒绝。
两项实际检查全部通过，CP749 磁盘重载、续跑和从头重放的状态与事件完全相等，
报告为 `validation/campaign/chapter08_joint_v4/flame_flag_peer_v1.json`。
它只证明具体旗标传递和其他修饰保留，不能计为 JT8-3 整关。

## 完整 Boss 的内容开发

普通攻击／灼烧者减伤和点燃／爆炸再点燃由两个内容开发子 agent 分别推进，
消费 `bsnake/requirements.v2.json` 的四模式、十一 Buff 模板及九项消费者要求。
嵌套的 `enemy_bsnake_s_2[reignite]` 模板另行固定，避免只看顶层列表漏掉真实节点。

爆炸范围已下载本轮固定提交的 `range_table.json`：
SHA `a98344d688a8933c4dd7ddaae3cb76c4347295359a18b60b918042cc2542d9d9`。
来源记录 `bsnake/range.source.v1.json` 保存 URL、提交、字节身份及 `x-5` 原始五格十字配置，
与旧离线单项比较相同。消费者使用固定配置，网格命中和来源原生方法解释仍单独验证。

完整阶段、关卡来源数值与用户实机反馈继续分别记账；正式进度仍以
[当前状态](CURRENT_STATUS.md) 的整关收据为准。

首次火雨、七阶段循环机关和波次跟踪的后续内容见
[火雨循环与波次跟踪](CHAPTER08_SCREEN_AND_LOOP.md)。

## 可重建源码

`tools/candidates/chapter08_joint_v4/manifest.json` 保存一文件增量和全部输出身份，
SHA `c0889e21269b0acd3682a0d075d2a33cba4e4492d9b8053e220518a48f289273`。
同目录重建工具已实际生成一致的 20e 候选。
旧 V3 的真实失败代码及报告保持可复核。
