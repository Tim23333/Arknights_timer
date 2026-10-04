# 十二人天赋、默认召唤资源与首关集成

本阶段继续固定十二人、标准主线0–17章末两关共36目标，正式验收仍0/36，完整原生干员仍0/12。
子agent按用户指定的gpt-6.1-sol / medium并行开发和交叉复核，root整合与修复通用领域。

## 当前可执行内容

攻击侧六人天赋和支援侧六人天赋已合入 `packages/campaign/squad.integrated.json` 的正式单位依赖闭包。
固定E2 70/潜一/信赖100/指定技能专三/无模组的基础HP/ATK/DEF/费用与所选SP机制继续保留，
原型HP/ATK/坐标、合成对手和测试移动能力不进入编队。
独立整合测试覆盖12名正式单位均带天赋模型、白面鸮加速攻击侧时间SP且不替换陈的攻击SP、
风笛未驻场仍贡献编队初始SP、实际付款绑定召唤等行为。

`tools/build_mainline_model.py` 已生成可编译的0-10集成模型，包含35个原生出生条目、5种敌人、
4种近战combat攻击与1种保留被动属性的飞行敌人。真实地图、路线、原生8部署上限、费用/生命资源和
movement multiplier保留；无预定义、适用符文、global Buff与branch的检查严格拒绝未知输入。
非适用符文保留为inactive来源。完整选项、原生时钟和机制审查仍待完成。
文件位于 `packages/campaign/mainline_models/`，与尚有缺失引用的原始IR草稿分开保存，
状态为 `executable_partial_model_not_accepted`，不会进入正式验收分子。

原始0-10 story TextAsset已实读并校验SHA/字节界限，包含HEADER、三个PopupDialog和Blocker。
`tools/build_mainline_control_model.py` 将原生STORY与DISPLAY_ENEMY_INFO逐条转换为观察事件，
保存敌人预览route10。headless_ack_zero_game_time_v1明确在同逻辑tick记录剧情/命名输入锁/解锁，
不假称模拟原生UI等待或已恢复暂停回调。独立测试实际执行完整事件序列与敌人提示。

## 资源来源与版本边界

官方CDN的固定2025-03-27资源清单为默认Mon3tr、温蒂水炮和夜莺幻影提供了实际battle tokens资源。
ZIP内AB的MD5和字节数与固定清单一致；archive自身MD5不被误当AB MD5。
默认chararts包只有立绘、skinpack只有服装资产，均未被冒充默认战斗资源。
提取器封存GameObject/MonoBehaviour/Animator/Spine的实际引用、原始脚本与SHA，
Mon3tr普攻f7、S3 f20，水炮普攻f1及弹道speed10已成为自动模型时钟；
Mon3tr死亡1200真伤/3秒晕眩与withdraw分离，幻影无攻击、零部署名额、HEALFREE/自损也有实际模型。
2025资源与固定2026-09-29表的完整版本对应尚未证明，客户端时钟与算法保持pending。

见 [攻击侧](ATTACK_TALENTS.md)、[支援侧](SUPPORT_TALENTS.md) 和
`packages/campaign/support_tokens.reference.json`。原生字段、模型策略和待核对项均保留。

## 通用底座及独立复核

新增damage.request与random.check契约，总命名契约75；数值仍由表达式、图或纯provider可替换。
来源before/接收方after damage hooks支持显式随机流、条件、优先级组、非递归追加包和资源分配；
highest SP、min sluggish、source-bound fragility避免叠加及不适用来源污染。
Buff回能使用emission冻结快照，动态amount_rule按真实正负增量冻结。
模式切换可明确reset攻击时钟并取消未launch的旧攻击，保留已launch弹道。

部署卡式召唤与普通deploy共用地形/占位/容量/实例/冷却规则，免费召唤paid_cost0，
付费召唤只能认领当前cast未分配的真实付款。治疗免疫同时影响候选选择和结算。
scheduledEffects/input_lock的时间、状态与事件参与事务、检查点和回放。

独立复核发现并推动修复追加包丢hook锁、别名分配相互覆盖、免费召唤凭空返费和
direct alias漏计实际伤害四处问题；root另发现幻影无lifecycle导致HP0仍在场并推动补足。
复核保持严格伤害、事件、随机与资源预期，没有skip/xfail或正式关卡自行放行。
见 [内核复核](M6_KERNEL_REVIEW.md)。

## 验证与下一步

本阶段的全套V2、修复后同身份0-1及0-10短程集成证据保存在 `validation/campaign/m6_final_*`。
较早基线因修复改变实现身份而拒绝回放；早期短测验证器自身调用quantize产生额外观察事件，
已改为读取原有调度任务统计出生守恒。两份原始非零日志保留，不被重写为通过。
最新最终结果以同名JSON中的passed、实现身份及原始log为准。

最终记录如下：

- [完整V2测试](../../validation/campaign/m6_final_tests_20261002.json)：885项全部通过，pytest耗时513.12秒；
  运行前后核心与测试源码身份一致。内容复核后的新3项及受影响套件另外定向13项通过24.62秒，
  见 [后续内容检查](../../validation/campaign/m6_post_review_stage_checks_20261002.json)。不将这两次记录伪称一次888项全测。
- [0-1最终回归](../../validation/campaign/m6_final_baseline_20261002.json)：tick2408终局、11击杀零漏怪；
  tick300检查点续跑与从头回放的状态、任务、随机和181,638事件一致；自定义伤害850/60也通过。
- [0-10最终短测](../../validation/campaign/m6_final_00_10_probe_20261002.json)：真实20秒/600tick，
  3条命令接受、5次原生出生、2击杀零漏怪、30次出生仍待执行；66,066事件与检查点/回放一致。
  正式验收false，终局仍running。当前包、程序指纹和runtime再次核对一致；
  验证器另保存原始package/commands bytes快照，便于源内容后续变更时保留复现输入。
- [首关内容独立审查](M6_STAGE_REVIEW.md)：35出生、117瓦片、17路线与12个正式单位依赖闭包核对，
  修复重量与缺口传播遗漏、原生options/seed审计记录及Mon3tr旧扣款clamp漏洞。
  实测DP5拒绝且保持5/无召唤，DP10成功且paid_cost10；未签发正式审批收据。

核心implementation digest为 `2ead42b3f048e1bcdcaffd78792e009a8db133b1aab43705e261ade692400321`。
早期短测有1次漏怪，提前一秒部署又被DP不足拒绝；对应原始记录均保留。
当前固定脚本按实际资源阶段在tick360部署风笛，不能借输入脚本悄悄增加开局DP。

0-11依赖规划已生成：37次出生、6种近战敌人、1个STORY与2个DISPLAY_ENEMY_INFO，
暂无非空预定义或适用符文；该规划仍不可执行，需单独转换和复核。

下一批先完成0-10全程操作与源选项/机制审查，闭合凯尔希治疗优先级、技能时钟/快照等剩余模型缺口，
建立独立审批证据后再推进0-11。随后按1-11/1-12起逐章补Boss、预放置、锁卡和地图机制。
0-1回归或0-10短程成功不提升36关的正式完成数。
