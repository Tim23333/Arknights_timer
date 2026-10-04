# 1-11 / 1-12 控制源审计与独立headless子集

新工具 `tools/build_chapter01_controls.py` 输出 `packages/campaign/chapter01_controls/{native.reference,model,assertions}.json`。它保存两关完整native level文档及控制/故事源，提供独立metadata delivery、输入锁窗口和NPC创建profile；**不生成完整关卡timeline，不宣称原生控制完成**。

原Chapter01审计SHA锁定为 `a242f94040c7f96d175056e6ceffa285ea10f60bec00db1ab7f354fe0739b0cd`。每个story TextAsset实际文件SHA、base64 payload SHA和UTF8解码脚本逐项比较。已有角色模型、源pin、reader/helper、所有核心/candidate及旧包均未修改。

## 真实控制索引与数量

| 关卡 | wave/fragment/action | 类型 | count / delay / interval | routeIndex | blockFragment |
|---|---|---|---|---:|---|
| 1-11 | 0/0/0 | STORY main_01-11_a | 1 / 0 / 1 | 0 | **true** |
| 1-11 | 0/1/0 | PREVIEW_CURSOR W | 1 / 0 / 1 | 1 | false |
| 1-11 | 0/1/2 | ACTIVATE_PREDEFINED Adnach | 1 / 2.99 / 1 | 3 | false |
| 1-11 | 0/1/3 | STORY main_01-11_b | 1 / 3 / 1 | 4 | false |
| 1-11 | 0/4/1 | DISPLAY_ENEMY_INFO rogue | 3 / 4 / 12 | 16 | false |
| 1-12 | 0/0/0 | STORY main_01-12 | 1 / 0 / 1 | 0 | false |
| 1-12 | 0/1/0 | DISPLAY_ENEMY_INFO W | 1 / 1 / 1 | 1 | false |
| 1-12 | 0/4/0 | DISPLAY_ENEMY_INFO mocock_2 | 1 / 3 / 1 | 15 | false |

每行完整managedByScheduler/dontBlockWave/autoPreviewRoute/autoDisplayEnemyInfo/randomType/refreshType/hiddenGroup等flags原样保留，没有删除blockFragment。上述delay都相对原fragment origin；STORY_a阻塞使后续真实origin未知，本批不将其展开为完整绝对时刻。

1-11数量为STORY2、PREVIEW1、ACTIVATE1、DISPLAY3；1-12为STORY1、DISPLAY2。这里DISPLAY3是一个action的三次repeat，不是三行不同action。

## Story源分类

1-11_a实际包含HEADER（is_skippable=true、is_autoable=false）、三个name赋值/UI文本、dialog、Blocker。它的native action确实blockFragment=true。

1-11_b HEADER为is_skippable=false、is_autoable=false、is_tutorial=true，含五个PopupDialog，animStyle均NoWait，并有Delay4/4/4/4/2，总声明时间18。Popup在显式模型中的offset分别0/4/8/12/16。

1-12含HEADER（skippable=true、autoable=false）、三个PopupDialog及Blocker。Blocker原生字段包括fadetime=.3、block=true、a=0。**UI overlay的block字段不能证明就是战斗全局input_lock**；fade duration、确认及game-time/wall-time语义仍未知。

参数只解析明确的ASCII key=value/quoted-string/number/bool，未知语法或重复字段严格报错。name文本、Popup文字、nickname占位及UI样式都作为opaque metadata，绝不从对白推导攻击、创建、锁卡或战斗指令；原始行号、raw line、参数和文本完整保存。

## 异步控制拒绝完整转换

当前Timeline的effects action同步执行后立即减remaining_actions，只有spawn拥有可退场的managed membership。它不能等待story确认、UI退出或异步control完成。因此：

- STORY_a的blockFragment必须保持model_gap。
- STORY_b与1-12 STORY即使blockFragment=false，managed-wave生命周期仍未证明，不能假定emit即完成。
- `require_complete(reference, level)` 对两关都明确拒绝完整控制timeline。
- 没有发 `story.finished` 或 `native.story.finished` 来伪造原生完成。

DISPLAY/PREVIEW的可执行作用仅为同步 **metadata observation**，全部sourceflags和route原文带入payload，`native_UI_render_or_action_completion=false`。它不声称恢复UI渲染/确认/managed lifetime。1-11 PREVIEW route1保存真实WALK及reachOffset；DISPLAY等占位E_NUM路线也保存，不能变成floor或执行移动路径。

## 独立headless窗口profile

另提供 `story_profile`，只用于独立模型实验：metadata即时ack，Delay作为logical game seconds，整段模型窗口inputlocked。它保留所有故事行，不跳过不可跳过HEADER；ack方式是声明的模型政策，并不是实现原生autoable/confirmation。

1-11_b模型0刻启用锁，按0/120/240/360/480刻观察Popup，540刻effect phase执行unlock并发 `model_window_ended`（明确native story未完成、fragment未释放）。命令1刻被拒；命令540刻在unlock的effect phase之前仍被拒，541刻接受。Timeline在初始signal内展开同刻actions，不能默认预先提交的t0 command排在锁之后；该顺序未声称原生回调行为。

这个standalone profile不能直接替换完整stage的异步story barrier。它只验证合法的通用input_lock、schedule及命令拒绝/释放能力，game-vs-wall-clock、战斗暂停和native callback仍client_pending。

## NPC activation profile与预定义依赖

唯一ACTIVATE匹配1-11真实Adnach实例：E0LV20/favor0/pot0、position(3,6)、RIGHT、hidden=true、alias=null、skillIndex0/mainSkillLvl1。routeIndex3是**E_NUM空占位**，不是NPC移动路线。

可执行profile选择“activation之前不存在actor；activation时从精零20级定义create一个active actor”。在独立fragment origin0场景，2.99秒按30Hz向上取整至90刻，之前零birth、之后恰一birth，HP677/SP0/ATK199/DEF74、位置与方向正确；不使用route_hidden。spawn无alias时保持原生aliasNone；以创建事件/runtime ID观察，不伪造charKey alias。

模型birth与预先存在的hidden dormant NPC不同：SP/被动/aura/生存时钟之前不运行，runtime.deployed仍false。原生registry、隐藏激活、deployed状态和施法权限未实现。没有绝对stage activation时间claim，也没有猜DP收费或卡牌归属。原NPC模型完整metadata与其缺口嵌入新model，未升级为完整干员。

1-11保留12项原生characterCards（原字典结构）。**1-12 characterCards是真实空字典，tokenInsts却有一个trap_002_emp**：E0LV10/favor0/pot0、(2,5)UP、hidden=false、alias=null、skillIndex0/mainSkillLvl1。其可执行定义、category/filter、aura/SP受益与生命周期均未转换，只保留源和依赖gap；不猜一次性销毁。用户fixed12deck是另一个组合输入，不等于原生卡牌或装置。

## 实际验证与冻结

generate / `--check` 实际通过；独立套件 **6 passed in 2.04s**，日志 `tools/experiments/chapter01_controls/final.log`。验证包括flags/indices/count守恒、UI文字不作为damage、native完成信号不存在、锁参数错误编译拒绝、540/541命令边界、DISPLAY repeat120/480/840、NPC零birth→一birth和完整CP/commands replay。

实际导入锁定 `D:/Arknights/Arknights_timer/unpack_work/campaign_m12_projection_candidate/ark_sim/__init__.py`，前后implementation为 `bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11`。没有修改正在全测的bd60或任何其他核心，没有运行整关、签审批或提升formal36。

| 产物 | SHA256 |
|---|---|
| builder | `44863a7e4ff2c68aa340bb3e5991ab8e74636fe96614e7c0f65a58b600e11a84` |
| independent tests | `f0230309835e6b61b30dce5637e4b63080d6fdedb7b174f9950e5fc7cf321e91` |
| native.reference.json | `caa25dcdfbb2af5707a4d0d9ec86e8c73feec38fefdaad9481b5aa3df1ecc79a` |
| model.json | `ebd821beb558ea5ae6209278822ab5adc1dd35c6d8d821ef60401e8cfd5d788f` |
| assertions.json | `8e773cc6fec8562710bdbbc4827ead5dedf9cc7e179da7c5f20bddb89a9897c5` |

未提交推送。
