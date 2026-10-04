# 第八章火雨、循环机关与波次跟踪

本批内容继续使用隔离联合底座 `20e812…`，正式关卡计数与主底座仍见
[当前状态](CURRENT_STATUS.md)。所有子场景分别记账，不以一次火雨或一次机关遍历代表整关。

## 首次火雨

`bsnake/first_screen.module.v1.json` 已实际执行来源周期：公开致死请求在 tick1，
原 5 秒复活等待结束于 tick151；采用固定资源的恢复比例 .5 与 maxHP 增益 .5，
恢复 HP37500、maxHP75000、ATK1155。火雨从该时刻持续28秒。
十轮发射在 tick211、271、331、391、451、511、571、631、691、751，
受控三行场景共30颗弹道，RES40 下各造成693法伤。
火雨在 tick991 结束，切换模式1、重启状态机并获得15秒无敌，tick1441 到期。
真实 CP400 重载续跑与从头回放的完整状态及事件相等。

实际报告 `validation/campaign/chapter08_joint_v4/first_screen_author_v2.json` 为两项通过，168.12秒。
旧测试的 range 上界误写成11轮，失败报告保持原字节；修正后的期待仍为原生十轮。

后续 v2 保留原 BuffDuringCasting 的 `[22,5]`：
22 为 `UNMOVABLE_PRIVATE`，5 为 `INVINCIBLE`，9 才是 `INVISIBLE`。
不能把22命名为隐身。v2 内容 SHA 为
`8399a1e72249b1fc1225f55b8db45cf24f510faa26cfeb3af2b30998b8e18fc8`。
无敌期间的普通选择拒绝与可忽略选择限制的伤害拒绝分别验证；
普通技能在火雨期间的模式条件需在完整 Boss 仲裁组合中验证。

原生JT8-3九行地图的七条内部火球行，已构建为
`bsnake/first_screen.native7rows.v3.json`，28个弹道原型，SHA
`b06a59916372f1ad29c520d0aaadca2920a330cc5438f149a215f5a403ec8eb4`。
完整周期作者两项实际通过1072.41秒，十轮共70颗火球、70次693法伤，
原5秒复活、28秒火雨与15秒无敌边界保持，CP400磁盘续跑和从头重放完全相等。
报告 `validation/campaign/chapter08_joint_v4/first_screen_native7_author_v1.json`。
独立首轮七行与纯轨迹检查另存 `chapter08_native7rows_independent_v1`，
仅声明当前来源几何解释，不将其当客户端碰撞体校准。

当前 PRTS 说明首阶段恢复100%，原固定组件 `_hpRechargeRatio=.5`。
本批按固定来源显式保留37500的解释，并记录网站冲突，交用户后续核对。
28秒火雨、十轮两秒间隔及结束后的15秒无敌，与
[PRTS 黑蛇说明](https://prts.wiki/w/%E7%A7%91%E8%A5%BF%E5%88%87) 对照；不宣称已实机验证。

## 机关分支循环

原 SummonFlame 的 `MoveNextLevelBranch._isLoop=true`，
`LevelBranchTrigger._isLoop=1`。旧 `branch.profile.v2.json` 的非循环35次配置
是一次受控遍历，不能作为完整召唤机制。

新 `flame/loop.profile.v3.json` 使用原七阶段次序并启用循环，SHA为
`8e2f1afbdb2f136b6d01e86de604c4a919effdb3c6f9dd6c9612198589bb18da`。
原技能50秒冷却、75秒初始冷却保留。
在显式30000tick仿真上限内，保守预留21次请求、105次机关实例激活。
这是执行上限下的内存与身份预算，不能称作原生总库存。
上限耗尽时必须报告未完成，不得伪造关卡或分支终结。

原语受控八次请求已实际通过，产生40次激活，第八次回到第一阶段，
真实 CP27 重载续跑与从头回放相等。
这使用明确的静态测试实体与公开退场请求，只证明循环与实例复用；
原生25SP机关的长程来源场景单独运行。

## 预告与召唤

`bsnake/summon_hint.module.v4.json` 保存实际七组注册键、Hint／HintCountdown 两个角色、
27秒单次倒计时、Skill3的27帧动作、50／75秒来源时钟和 modulo7游标。
新模块 SHA 为 `d6718d3a7ac9fe5b0a04f7f03548d263331c963c1558ccd160527c609219fa15`。
视觉观察事件携带原注册键和效果ID；完整节点时序与客户端视觉仍为显式可替换解释。

受控八次内部召唤请求和倒计时回调已实际完成，两项通过18.63秒，
CP650 重载续跑至1550与从头回放完整相等。
它把来源CD替换成受控短时钟以检验回调和游标，不能作为原生50／75秒时钟通过。
原生时钟与完整 Boss 仲裁另行验证。

## 下一波跟踪的真实缺口

源 BSON `track_at_next_wave_when_buff_finish` 的请求为：

```json
{
  "finish_and_skip": false,
  "track_source_at_next_wave": true,
  "track_source_wave_delta": 0,
  "track_all_managed_at_next_wave": false
}
```

当前通用 `finish_timeline_wave` 校验仅支持四个选项均为默认值。
对字面源请求的函数校验及实际内容编译都返回
`Unimplemented timeline finish flag combination`。
反例报告为 `validation/campaign/chapter08_wave_track_source_counter_v1/report.json`，
SHA `efccfc41d61286bd4e82858d97cb306d35475a2f031616a3df15de4910cdbd07`。
下一版将把存活的真实来源移交下一波成员记录，并验证未来出生、延迟、一次结算和回放。
