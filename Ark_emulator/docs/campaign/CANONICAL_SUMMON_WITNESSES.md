# 未部署召唤组的 canonical 机制见证

本批保持 primary V2 core `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`、旧包及前21项冻结见证不变。新工具/pytest小场景直接读取canonical定义；仅添加明确的合成刺激、初态伤口/SP/位置/DP与几何，不替换干员、技能、人才或token能力。固定deck12与36关目标不缩小。

共用 `tools/canonical_summon_witness_support.py` 保存开始/结束源身份、实际内容SHA、配置、实现、test/helper SHA、完整输入命令与初态、实体ID/owner/HP/SP、伤害/治疗/中断/出生/退场/阻挡等实际事件，并执行完整snapshot的checkpoint/restore与命令replay。证据使用campaign_progress可读取的test字段，明确 `review_receipt=false, formal_approval=false`；不是审批收据或完整stage胜利证明。

## 凯尔希与Mon3tr

入口 `tools/witness_canonical_kalts.py`、`tests_v2/test_canonical_kalts.py`，原输入 `level_main_00-10.m8_roster.json` SHA `7604b67eb0d226f96e15bf567799dd8daf97857718b62a075ba5615c5c13b49a`。

独立固定数字：凯尔希HP1996/ATK468；Mon3tr HP5177/ATK1345/DEF389/block3、DP10/cool25；normal f7、S3 f20均来自exact外部2025default绑定，2026本地对应仍pending；不使用char4179替代，也不发明token技能ID。

已实际执行source/config、DP/owned支付与第二只/容量/payload失败原子性、owner隔离、host无token不回SP、token退场后live host清SP、owner退场清token、normal f7物伤1245（DEF100）、S3保留next_attack时钟后tick80 true衰减值、死亡1200与3秒stun、withdraw排除死亡爆炸/CD25、20秒无kill失50%maxHP、ownkill清marker免罚。击杀免罚不是凭空添加HP/SP回复。20秒期间曲线为source-backed显式linear_remaining；原生逐帧FSM/改攻速缩放继续pending。

三个实际治疗分类分别通过：自伤HP1000时先self，f13加召唤阻攻tick0后tick14回复468；own Mon损伤500而foreign Mon损伤5000时仍先own（true score .9034小于foreign2.0342），tick20回复468；own满血时foreign fallback tick27回复468。该偏好是M7字段64支持的semantic profile，未把缺方法体的native selector算法提升已恢复。

独立发现真实模型阻断：SP门 `selector=owned_mon3tr, interrupt_when_empty=true` 调用全cast interrupt，没有own时也取消ordinary heal。保存 `canonical_kalts_recovery_interrupt_gap.m8_roster.json`，包含foreign受伤、normal启动2/tick3被取消/无治疗的原输入及命令。独立预期保持foreign tick27可治疗，未改SPspec临时绕过。Root随后M10按具体S3名单闭合此门，见下面的candidate复核。

原f8仅有明确分组通过的证据，不能把含该失败的整个Kalts组标通过。下一轮需用M10最终输入将全部canonical用例重新导出；目前没有除此以外已实证的新Kalts阻断。其他unit击杀的marker、出治疗范围DEF归零等可继续作为补充边界，不能从旧prototype直接升级新整合证据。

## 夜莺与幻影

入口 `tools/witness_canonical_night.py`、`tests_v2/test_canonical_night.py`。player定义仍是同一roster；taunt整合最终输入为 `level_main_00-10.m8_targeting_v2.json`，SHA `aa272589e6b02349855fe7c2632e04c27270f5454874bc9deca460ab429a70c3`。原生比较器/仇恨正文及动态taunt modifier adapter继续pending，不宣称完整native targeting。

固定数字：夜莺HP1624/ATK404/DEF162/RES5；S3 ATK+80%/RES+150%/arts dodge25%，三伤员AttackC f27、interval2.85；因此actual每包727.2，首三包tick27、第二批tick113重选四名伤员。合成MRES10友军的基础光环+15后S3为62.5，100arts未闪为37.5；physical不消耗该arts RNG。独立SHA/MTprofile样本验证概率，未称客户端RNG已对应。

幻影source为token_10003_cgbird_bird：E270 HP5326/RES75/taunt1，无普通攻击；两卡，每次card1+DP5同原子，capacity0允许占满常规容量时仍放两个。实际命令验证DP不足/缺payload回滚、禁止普通heal、regen独立回补、每秒maxHP3%=159.78、HP流失及敌杀均真正退场、owner退场停止后续HPdrop。卡片native回补/再取回、是否另有native定时器/HEALFREE细分正文/外部2025与本地2026版本对齐仍保留；模型使用已声明的born2池及HP流失生命周期，不冒充未取得的算法。

Taunt原包只有数字没有生产score绑定。实际修正后的旧probe发表普通dummy4，Bird5未获优先，保存 `canonical_night_taunt_actual_gap.m8_roster.json`。初次9/1历史的taunt夹具缺attack_interval，不能作为发表target的证明；该错误单列历史。

Root v1复制旧support player评分后发现方向反了：真实WALK形成enemy3.blocked_by=4，但tick3仍选Bird5，保存 `canonical_night_targeting_review.m8_targeting.json`。v2改为enemy source.blocked_by==candidate.id。新独立fixture克隆production gopro的完整rules，不注入临时测试score；Bird较远优先、真实blocker优先、来源退场重选与已声明candidate过滤 **3 passed in6.65s**。过滤证明只覆盖明确tag/alive资格；没有将其称为native hidden/camouflage实现。

还增加S3真实60秒半开：1799tick100arts受62.5RES为37.5并采样，1800tick恢复25RES为75且无额外S3 dodge采样，mode回0。该用例须以实际完成的fresh artifact为准，不从时长字段自动盖章。

最终v2完整13case已真实通过，`canonical_night_witness.m8_targeting_v2.json` 的 `identity_stable=true`，60秒半开也完成完整checkpoint/replay。此前v1的失误/真实方向反例和原roster真实taunt反例均留作历史，不覆写为v2通过。默认Night pytest输入已改为v2；显式旧包仍保留原反例期望。

## 温蒂与水炮

入口 `tools/witness_canonical_weedy.py`、`tests_v2/test_canonical_weedy.py`；当前roster SHA7604b…原定义未改。完整10个独立case已实际通过并保存 `canonical_weedy_witness.m8_roster.json`。

独立数字：温蒂HP2027/ATK693/DEF424，S3cost33、倍率3.5；水炮ATK561、interval2.4、normal f1、speed10、force bonus1、DP5/capacity0/lifetime20/CD35。normal在距1时f1+3 travel=tick4，DEF100结算461。near3秒SPpulse及manhattan4之外不返SP均实际验证，空部署cast暂停一份periodic quantum后first tick30，与未施放时tick29积分不同。

host与owned S3联动实际分别用自己ATK且只有host付33SP；MRES20时水炮1570.8/host1940.4，捕获身份与时钟不同而不是一个数值模板。rupture只保留一个EXTEND lease。推力是明确可替换的historical distance/speed table，native曲线pending；质量0的D3.33058独立核对真实路径与1200/格true damage，不能仅互相比较两个错误actual。壁障剪裁至约.5格，数值累计600的float误差1.16e-10以1e-6容差处理，未放宽物理上界到名义全推距。21tick移除lease对两份D/35的路径冲刷未结末段，后续运动不重复收费。

20秒真实lifetime600退场后CD35拒绝立即再放，owner退场清理/SP停止。空目标显式profile为允许命令、付33、无前射projectile，实际执行并记录；原生allowNoTarget字段允许施放，不足以证明native forward-projectile/碰撞/invalid FSM算法。该source解释与原生未知不删除，不升级完整native技能。

最终完整 **10 passed in62.66s**，开始/结束input/source/helper/core稳定。不是仅把旧15个prototype测试作为新canonical见证。

## M10候选独立交叉复核

候选root `D:/Arknights/Arknights_timer/unpack_work/campaign_m10_cast_freeze_candidate`，真实digest `f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e`。`tools/review_m10_resource_precision.py` 在导入primary helper前预载候选ark_sim，并在test核api.__file__，未补丁primary。

`tests_v2/test_m10_resource_precision_review.py` 原独立期待验证Chen S1风up中120tick人才SP0，normal158启动/171首hit后一次SP1（第二hit188不再返）；Kalts无own时foreign27tick正常heal；loss仅中断S3而普通self heal14tick仍468、SP清0；纯snapshot rule在cancel任务后除零，完整checkpoint（world/tasks/events/RNG）回滚。未用catalog actual倒推expected，也未使用stub simulator/handler。

仅2字段包 `level_main_00-10.m10_resource_precision.json` SHA `d694705f9d6e3793ffd5e33e525adeace9c0478e4a6c627e50e5d575d5ea0637`：**4 passed in7.67s**；综合 `level_main_00-10.m10.json` SHA `2b7fe8d63a30765614a63a9914b6c3a59248600663f85972527491390bd44de8`：**4 passed in7.64s**。分别保存 `m10_resource_precision_independent_review.json`、`m10_combined_resource_independent_review.json`。原始期望构造时unsupported len/布尔mapping/欠metadata以及首hit时点修正均属fixture错误，不列核心失败；首次错误历史保留。

这些fresh机制证据独立于Root更早收集的全suite。任何未被当时collect的新test/helper版本不会被揉入其全套计数。formal approval继续0，原36关及完整12人闭包仍由七门审查。
