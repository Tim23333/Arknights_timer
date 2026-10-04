# 支援天赋与持续治疗原型

固定 E2/70、潜能1、信赖100、选技专三、无装备。构建工具读取规范源表、六个实际 charpack、选技 prefab、原始 BSON buff_template_data 和 buff_table 原始二进制。只输出 V2 内容，不导入 V1 战斗运行时。

`talents.support.json` 是部分实现的模型包。六人的11个当前适用天赋原文、黑板、组件和依赖均封存；所有 applicable source 并不等于所有 applicable behavior 已实现。包不生成审批收据，不证明完整干员或正式主线胜利。

| 对象 | 原始证据与已运行模型 | 尚未闭合 |
|---|---|---|
| 塞雷娅第一天赋 | E2 黑板 interval20、max_stack_cnt5、atk.05、def.04；BSON demkni_t_1 创建无限寿命 STACK buff、ATK/DEF MULTIPLIER。time_layers staircase 从实例驻场时钟每20秒增加一层，100秒到 ATK+25%/DEF+20%，继续停留不再增加。 | charpack 默认 interval30 与官方黑板20的原生参数覆盖路径尚需客户端时钟见证；模型显式选定黑板合同，没有把30秒写成20秒的原始字段。 |
| 塞雷娅第二天赋 | BSON ON_OUTPUT_MODIFIER→IsHeal→ModifySp，目标MODIFIER_TARGET，spMaskALL，forcefalse。模型仅在持有者自己 healing.accepted 时为真实 event_target 恢复SP1；无SP资源跳过、recipient恢复冻结时跳过。 | 原生输出modifier与accepted heal的钩子顺序、零实际治疗及免疫边界仍需原生对照。 regeneration不被当成治疗事件。 |
| 白面鸮天赋 | E2+.3/秒；全场 charpack validator professionMask639，spRecover modifier14/formula0。全场 time型我方成员增益；sp_recovery层max_add，与同类效果取最高。撤退移除来源成员。 | Native DB packed enum/flag 的完整版本规范化；模型用官方和priority黑板证据定义最高值合同。 |
| 白面鸮S2 | M3 BB base_attack_time=-2.1；实际prefab属性8/formula0直接间隔修正，模板switch_mode_restart_fsm；mode1三目标治疗，preDelay约.2。模型base2.85-2.1=.75，每次自动cast重选三名伤员并周期执行，SP100/初始85/40秒冻结和同步到期恢复已实现。 | 没找到渐变/ramp字段，绝不造线性曲线。攻击首时钟、FSM restart、动画随间隔缩放及终点已发出治疗包的原生规则仍pending。逻辑帧向上量化使.75秒成为23帧，predelay成为7帧，均为模型调度合同。 |
| 铃兰第一天赋 | E2 SUPPORT professionMask16，+.4/秒，与白面+.3重叠时SUPPORT总恢复1.4，其它职业1.3，不变成1.7。 | 仅time恢复接属性规则，攻击/受击event恢复不能被该光环错误加速；编队集成必须保留原资源selector gate及freeze配置。 |
| 铃兰第二天赋 | BSON lisa_t_2 每约.03秒查询sluggish，创建自身derived weak[inf]，没有sluggish则清派生；DB weak[inf]指向damage_scale[input]，priority key damage_scale，BSON mask ANY_ATTACK_EXCEPT_ELEMENT、isStackablefalse。模型用实际active Buff定义ID查询slow，独立来源动态成员通过group=fragility按eligible priority只执行一次；被动1.2/S3 1.4源绑定常数，混合alloc只放大HP部分，盾charge保持。S3每秒按.2ATK再生，独立sluggish层min_ratio防多来源负速。 | 原生.03扫描生成/清除derived weak与模型伤害包时刻条件检查的区别仍pending。随机/冻结之外的原生状态免疫、多个不同减速类型组合尚需对照。 |
| 夜莺第一天赋 | +15RES；实际 charpack infinite aura independentCharacterSource1、leave/detach清理。V2动态范围成员按独立parent施加flat15，移动出入和来源撤退同步清理。 | 既有单父源范围模型通过；多个同角色来源的原生覆盖细则需进一步来源校验，不能由一次通关推出。 |
| 夜莺S3 | atk+.8、自身切mode1、三目标Attack_C通过精确Animator→Spine绑定恢复27帧/.9秒，持续治疗、范围扩大、成员RES+150%已运行。evade_magic BSON仅MAGICAL/ALL；after hook真实imp样本<.25拒绝HP及allocation。物理伤害不抽法闪样本。 | 原生随机流及抽样顺序、FSM首攻击/动画速度、投射物与原生回调顺序需对照。模型已抽样不表示客户端概率轨迹一致。 |
| 夜莺第二天赋 | 当前适用cnt2及token_10003_cgbird_bird原文与官方外部default prefab已恢复。空attack/trigger指针证明不能攻击，block0/occupied count0；固定E270插值HP5326、RES75、tauntLevel1/cost5/respawn20。source资源bird_cards2和battle DP5同步原子付款，HP标healing_allowedfalse，source BSON evade_physical `.3`与每秒PURE maxHP ratio`.03`驱动真实hook/HP自损。补了通用lifecycle policy；周期耗尽和真实敌伤致死均使HP0/aliveFalse并发entity.died。纯targeting.score显式权重优先taunt1且checkpoint/replay一致。 | 原生born卡牌回补/owner-card共用冷却、嘲讽权重与优先级、skipModifierEvent与原生回调仍pending。固定fixture spawn不证明payload部署的地形/占位/容量约束。属性75为基础值，进入Night本体或S3光环会按真实成员叠加RES。 |
| 凯尔希第一、第二天赋 | 精确Mon3tr token关联/固定stat/范围外DEF0/owned召唤和绑定S3已有历史 skills.kalts.json模型。本轮恢复官方外部2025聚合包的default token prefab/SingleSpineAnimator/Spine：正常Attack f7、S2 Skill f11、S3 Skill_2 f20。新独立definition overrides将历史manual probes改为真正automatic_attack/auto_only，保持interval2/effective speed与block3、源表range1-1。死亡BSON ON_OWNER_KILLED/CheckContainsBuff(kalts_t_2)、实际BslimeTalent_1 FixedValueDamage PURE、token自身E2/pot1 BB value1200/stun3/range x-4共同支持死亡AoE/3秒控制模型，withdraw不触发。 | 外部2025与本地2026版本吻合仍pending；原生FSM切换/动画速度/首次时钟、死亡projectile reached/hit时序、stun抵抗免疫仍pending。模型死亡效果在entity.died reaction执行，不能冒充原生投射物帧。历史文件不变，不用char_4179替身。 |
| 温蒂两项天赋 | 当前cnt1/20秒水炮与强化来源全部封存；skills.weedy.json已有owned炮、3秒回SP、增强推力与S3联动模型。本轮增加default Cannon Attack_Loop f1自动packet，精确projectile_weedy_cannon mover speed10，1格距离模型到t4落地；E270 ATK561/interval2.4/effective AS1，物伤成功后按既有源推力模型force0+强化1。token override声明capacity0/baseCost5/cooldown35/terrainboth。 | 原生begin/loop交接、projectile属性采样时点与原生力学仍pending。旧selected Skill3联动定义保持历史，不从operator Skill_3名字猜Cannon动画；新增自动normal override独立来源记录。 |

## 原始依赖与读取边界

BSON 子集保留原始 document bytes/base64、偏移、SHA及严格有界解析结果，类名只作数据。spRecover、weak[inf]、sluggish[inf] 的 FlatBuffers DB 保存整份26KB原始 bytes、hash、解析辅助源码身份和选定table/field偏移。研究辅助通用 decode 对 packed bool/enum 会产生整数字，并可能把短标量误判成向量；这些字段明确标 `indexed_research_decode_packed_flags_not_normalized`，不能供公式取值。当前 dump 多了 remainingTimeKey，完整字段布局不可按新dump索引直接套旧资产。本模型用已经明确的BSON图、charpack数值、官方选定黑板，未执行未知研究decode。

Mon3tr公开来源调查： [PRTS默认模型页面](https://prts.wiki/w/Mon3tr(%E5%87%AF%E5%B0%94%E5%B8%8C%E7%9A%84%E5%8F%AC%E5%94%A4%E7%89%A9)/spine) 指向精确默认token路径；访问其静态skel遇到SSL EOF。[ArknightsAssets下载清单固定commit](https://github.com/ArknightsAssets/NewAssets/blob/f9453cd31ec03aad10be4409af95eb1ac2fdee5f/hot_update_list-cn.json) version25-03-27-16-19-10-4d4819记录 chararts/token_10002_kalts_mon3tr.ab（MD5 fb0322b74133604fb028c7dd6acf2106），实读仅portrait/UI；skinpack则仅boc6。没有把它们或[fexli时装资源](https://github.com/fexli/ArknightsResource/tree/d0b5af0b004b044d322397ce5ae79632b6d9fcdd/spine/token_10002_kalts_mon3tr)替换默认模型。

真正来源是同manifest的 `battle/prefabs/[uc]tokens.ab`，原AB长度9824830、MD5 `9e1440026259ebe74be054962e2bd656`、SHA256 `b9f16db4bfc8e8c880a0f90a1a7a74eda3b47c2188d0a151e5239d154716d475`。root定向curl获取官方CDN ZIP并验证解压AB；ZIP hash与AB hash独立记录。`tools/extract_campaign_support_token_sources.py` 离线校验精确ABbytes/MD5/SHA，要求唯一default GO，沿Entity→Animator→Renderer→SkeletonDataAsset→TextAsset取源，不按名字fallback。保存原始payload/base64/hash、源映射、所有必要原生组件、完整官方token表，以及私有BE reader/安装源码身份。Mon3tr骨骼1253740051363327079确为default3.8.99/FPS30，f7/11/20经float32同位重编码证明。温蒂cannon实际Attack_Loop/Down_Loop f1及默认双面源也保存，原生begin/loop切换时钟仍pending。Night幻影明确default无attack指针/occupied count0/HEALFREE flag7，与source属性/BSON共同支撑上述实际模型。

`source_evidence.mon3tr_external_attack_overrides` 给整合器提供 token_entity、ability_overrides、selector、additional_buffs/additional_selectors。`mon3tr_model_fixture()` 在内存中合并历史包运行验证，旧skills.kalts.json不变。保留原next_attack模型时钟：normal首包t7、再包t67；t8启动S3后，下次cast仍t60，S3包在t80，真实伤害按当前时钟衰减为4422.36。该具体模型策略可复现，未称原生首次Skill_2时钟已校准。

## 接口与验证

```powershell
..\.venv\Scripts\python.exe tools/build_campaign_support_talents.py
..\.venv\Scripts\python.exe tools/extract_campaign_support_token_sources.py --check
..\.venv\Scripts\python.exe tools/build_campaign_support_talents.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/talents.support.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_support_talents.py -q
```

已有行为测试实际检查驻场边界/上限、新实例重置、动态RES成员、持续三目标/重选、mode半开结束、SP冻结、最高光环、治疗返SP源归属、真实法闪样本，并进行40秒持续技能检查点与输入回放。长验证只在同一V2实现身份完成后算当前证据；最终结果在冻结后补记。

最终冻结验证：**28 passed in 143.21s**，两构建工具 `--check` 均通过，支持包CLI实际90 definitions/47 rules。涵盖上述支援机制以及Mon3tr自动帧/死亡/withdraw排除/回放、Cannon弹道延迟、Bird支付/HEALFREE/嘲讽/真死亡。较早的26例在Bird lifecycle补充前通过，不代替这次28例；运行途中改动造成的fingerprint拒绝、旧fixture断言失败均不算新身份通过。

当前V2 runtime fingerprint：`9a6ee56462d8f5088b0dc7c703abcbebf5e4f9bf491f2121bc3c68754d0c2c01`。

| 冻结文件 | SHA256 |
|---|---|
| tools/build_campaign_support_talents.py | ba5a9b1ada8077ca5f2cfbac01c4fa43cc022c5429b0865f49b2f1d2d3752391 |
| tools/extract_campaign_support_token_sources.py | 94df4f79414a2b8d2e4954a0889c997dbbf39b8ab17cb5476cea6694cc4f2a33 |
| packages/campaign/talents.support.json | 46e28d0783d6bdeaa3b528a08ea1e7888b51785314ca4fa0a8ccfcc788db36d0 |
| packages/campaign/support_tokens.reference.json | a0f8ecd92e11e7f63cb3d129b505ea5ba18eaebdc23660679571fc9c5f34497e |
| tests_v2/test_support_talents.py | f8215589b8f6fe056669aa0ff551d407bbe3e5af956533d8db53175fbd74d85f |

以上是source/model验证，无formal approval。外部2025来源与本地2026吻合、原生回调/动画速度/RNG、正式关卡执行及客户端对照分别保留gap，不通过测试数或通关结果自动升级。

集成时只取已验证的buff/selector/rule与选定能力；为time型资源绑定 `rule/support_time_sp`，追加 `sp_recovery` 属性层并保留原属性层、owner gate和freeze配置。Saria/Suzu天赋、Night aura和selected healing须保持各来源parent身份。fragile伤害取实际eligible hook的来源倍率，不能从不满足条件的modifier读全局最高；独立审阅发现并修复了这种ghost amplification，测试仍要求无效priority.8不能把100变180。包内同中心fixture只是测试输入，不能替代正式部署、owned卡牌或12人完整闭包。

整合显式接口在 `manifest.metadata`：`unit_patches` 以六个canonical `unit/char_*` 为键，仅用setdefault添加额外属性并追加光环/派生资源/天赋能力；`skill_definition_overrides` 保持三项已选技能canonical ID并更新Plosis/Night基础normal的mode0条件，还导出Mon3tr原probe IDs的自动定义；`token_definition_overrides` 明确 `unit/kalts_mon3tr_model`、`unit/campaign_weedy_cannon`、`unit/support_night_bird`。所有补充能力/Buff/selector在顶层提供。Mon/Weedy历史包中的必要规则由已有源模块闭包提供，默认token成长HP/ATK/DEF等不覆盖为fixture值。召唤输入位置由整合工具转显式payload；spawn eligibility/capacity/occupied在正式整合中另测，本支持fixture不自行宣称通过。

## 独立交叉审阅与修复记录

攻击侧 `tools/build_campaign_attack_talents.py`、`talents.attack.json` 实际只读交叉执行33例，15.53秒全过。读取规范表/6 charpacks/9 BSON依赖及声明范围，核查Chen SP类型限制、Lisk独立随机邻居与无候选不抽样、Eyja float RandomSetter与自动周期模型/未校准firstoffset声明，未发现所声明scope内新的阻断。后续原生RNG、出场回调顺序和完整talent/animation模型不能由这33例自行批准。

支援交叉审阅发现两项真实问题，保留修前反例并修复：inactive fragile hook的全局最大modifier曾造成ghost180，改source-bound eligible倍率后仍120；Buff事件SP恢复曾在同tick heal.accepted后先finish再react时从live判断而错误加SP1，root通用改为发出时刻冻结快照，独立同刻测试仍要求SP0。另root审阅指出幻影缺lifecycle，已补policy并加入HP自损/敌伤两条真死亡反例。混合shield/HP新allocation canonicalization曾让alias目标HP实际扣120却damage.accepted报0；root统一Effect目标UID，独立仍要求120且charge只扣1。
