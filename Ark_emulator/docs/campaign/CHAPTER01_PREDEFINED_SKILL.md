# 1-11 安德切尔所选等级1技能：表驱动子集

新工具 `tools/build_chapter01_predefined_skill.py` 将冻结的精零20级NPC模型与表驱动攻击增益技能组合到 `packages/campaign/chapter01_predefines/skill_model/`。原NPC source/model/assertions与旧helpers均未覆盖。状态为 **partial NPC normal + selected skill model**，不是完整NPC、原生脚本激活或整关通过。

## 原始选技与缺失模板

源输入锁定旧 `chapter01_predefines/native.reference.json` SHA `15eb6edf057af42e1c03acf441cc44852f1a3b4aefd511dd23428fcead1413e6` 和NPC model SHA `4eb40df9ef979f54f289c099b78723da61fc49d00fc88fcdafb1ace3c77b779e`。任何漂移直接拒绝。表锁的公开commit、表SHA、缓存身份和原读器身份均继承保存；不重新解释旧证据为新客户端校准。

| 原生字段 | 等级1真实值 |
|---|---|
| selected skill | `skcom_atk_up[1]` |
| prefabId | `skcom_atk_up` |
| skillType | MANUAL |
| spType | INCREASE_WITH_TIME |
| spCost / initSp | **50 / 0** |
| increment / maxChargeTime | 1 / 1 |
| duration / durationType | 20 / NONE |
| rangeId | null |
| blackboard | 唯一 `atk=0.1, valueStr=null` |

模型遵守MANUAL，不自动满SP启动。源 `selected_skill_prefab_sources` 为空；生成器如实保留，**没有恢复 `skcom_atk_up` 原生prefab/BSON模板或方法体**。文字描述不参与公式或时点推断。`durationType=NONE` 原值保留；本批显式使用duration20作为模型窗口，不声称恢复了该枚举的完整原生驱动语义。

## 可替换运行profile

profile `adnach_level1_additive_ATK_ratio_periodic_SP_cast_window_v1` 定义：

- 在标准属性规则的 `direct_ratio` 层施加ATK＋0.1。模型有效ATK＝199×1.1＝218.9，不对Buff后的值再次取整。原生字段应用层、取整顺序未校准。
- SP初始0、容量50，周期1秒恢复increment1，支付50。周期时钟含tick0：29刻首次恢复，1499刻累计50。此离散恢复profile是模型选择，原生SP计时正文未恢复。
- 手动施放先同事务支付并apply_buff，持续20秒，`blocks_attacks=false`。不改变普通攻击模式、范围、帧、弹道或时钟；不添加缺证据的reset/cancel/额外攻击。
- Buff为半开20秒窗口。`recovery_freeze_abilities` 只列出所选技能，保留普通automatic_attack的SP恢复。原生 `_allowSpRecoveryWhenAffecting` 没有在缺失模板中恢复；冻结策略和cast结束顺序明确为模型profile。
- 20秒能力cast在结束任务前仍冻结SP，Buff先在phase0过期。t0施放时，buff最后一次攻击伤害在582刻，612刻普攻恢复169；能力完成后下一SP周期在630刻得到1。没有将该同刻次序宣称为客户端确证。

所选技能复用真实NPC ATK199、DEF74、HP677、原生range3-1十格、OnAttack9帧与crossbow速度10。已有normal的source属性采样是at_hit：t9已经launch、t10技能开启时，t12impact可以读取当前Buff增益。独立测试确实只看到原t9一发，没有重置或重复发弹。

## 实际验证

generate / `--check` 均实际通过；builder模型断言验证了payment50、技能期SP0、188.9伤害、20包增益、结束后169伤害、下一周期SP1、SP不足拒绝以及满SP不自动启动。

核心短场景从fixture初始SP50施放，fixture元数据明确这项覆盖用于支付/窗口测试；生产model初始SP仍0。真实初始SP0的另一独立场景实际恢复到50，期间普通攻击不会冻结SP。

20秒窗口伤害独立计算为218.9−30＝188.9，比普通199−30＝169增19.9。另一DEF100反例期待118.9并通过。SP0与SP49不足均拒绝，没有部分支付或Buff残留；施放期间再次技能拒绝，遵守冻结标记的外部＋5SP也不恢复。原攻击在技能开启前launch时仍保留，仅按模型live属性在impact读取增益。

`tools/experiments/chapter01_predefine/test_predefined_skill.py` 是本批新的独立subprocess套件，不进入历史冻结M8全套。测试来源精确值、真实初始恢复/普通攻击不冻结、独立DEF公式、重复施放/主动正恢复冻结、既有攻击不重置，以及SP49边界拒绝。完整CP恢复与commands replay覆盖记录的手动技能命令，完整snapshot一致；没有将直接ctx状态写入冒充command replay。

最终同源码独立测试 **6 passed in 13.25s**（0fail/0skip）；最终builder `--check` 实际通过。结构化测试结果另存 `test.report.json`，仅记录本批模型验证。

实际导入始终为：

`D:/Arknights/Arknights_timer/unpack_work/campaign_m10_cast_freeze_candidate/ark_sim/__init__.py`

身份为 `f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e`；运行前后digest均校验。不使用已经提升的primary，也未改任何核心或candidate。

## 组合依赖与诚实边界

新model沿用entity `unit/ch1_predefined_adnach_e0_l20`，含原normal和唯一selected skill。替换旧NPC定义时整体导入新entity/abilities/selectors/buffs，不再追加第二份normal。

完整原始NPC `hidden=true`、position(3,6)/RIGHT、ACTIVATE_PREDEFINED控制和12张原生卡牌保存在新source中。没有转换其激活时点、routeIndex3、PREVIEW/STORY或用户固定12卡组覆盖政策；这些仍依赖后续关卡组合。技能命令仅是可执行模型输入，不是恢复了NPC剧情权限。

尚未证明的原生属性公式、Buff后整数取整、SP冻结/恢复驱动、启动动画、攻击重置/FSM、模板/BSON和脚本激活均单列source_gap/client_pending。不称NPC完整，不运行整关、不生成审批收据，formal36状态不变。

## SHA256

| 文件 | 冻结SHA256 |
|---|---|
| builder | `6305f205b2f8fbea51986852921248003d7287b2354a700c6520ef06bd98498d` |
| independent tests | `0851364e835a6f65e203f752f233d629384333e1ba22eed7355c56353eb96450` |
| skill native.reference.json | `402214d32c572e4f0ff0d6161fd5710f2cbf14c1b2a04ac9d844f205c7f98de3` |
| model.json | `e8a5b0114907b7f16977d7b061615c7501c59c072731784d53da81271b5d5b70` |
| probe.json | `d65b1be74f999eab2ed6aee47a59b25e73436bb5e4712aec886884e7eb899694` |
| assertions.json | `4f0949c164dedcf30b4b411197fccc1d00da5810b7a318a666b30e209cf780ae` |

没有提交推送。
