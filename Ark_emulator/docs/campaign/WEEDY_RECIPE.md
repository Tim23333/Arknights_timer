# 温蒂固定 S3 与水炮：可执行模型、原始依据与未校准边界

`tools/build_weedy_skill_recipe.py` 生成 `packages/campaign/skills.weedy.json`。
这份模型不是只有 SP 占位：实际执行一发弹道、撞击处群伤、逐 tick 强制位移、实际路径长度真伤、
带 owner 的水炮生成/联动/强化推力、每3秒主 SP、20秒寿命和退场清理。
仍为 `selected_skill_model_partial`、official_unit_complete=false、client_validated=false。
`require_complete=True` 对未校准算法、未恢复水炮普通攻击/FSM等依赖明确拒绝，没有 formal approval receipt。

```powershell
..\.venv\Scripts\python.exe tools/build_weedy_skill_recipe.py
..\.venv\Scripts\python.exe tools/build_weedy_skill_recipe.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.weedy.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_weedy_skill_recipe.py -q
```

## 固定配置与原始来源

主人使用 normalized 的实际 E2/70、潜一、信赖100、S3专三、无模组配置，模型 ATK693。
所选标准 BB 为 force3、atk_scale3.5、duration8、dist1、value1200、interval0.066、stun0；
SP init20/cost33/time increment1，技能 duration=-1。
**1200 是每单位移动距离伤害系数，不能当推开1200格；8秒是 rupture，不能当施放冻结8秒。**

技能与水炮 M3 prefab 在冻结 CAB 组件闭包中核对，实际 projectileKey=projectile_weedy_s3、
damageType2、waitForAttackEvent1、waitForProjectileInvalid1，launch selector maxNum1/targetMotion3。
水炮所选 sktok_weedy_token levels[9] 的参数与宿主完全一致、SP成本0、isRemoteControlled1。
token selector postFilter11 为源距离近优先；host postFilter4 为仇恨降序，原生仇恨算法仍 pending。

使用 frame agent 的私有 BE reader 在温蒂自己 chararts 重新解析，不改共享/installed reader。
精确 Animator front/back 的 Skill_3→Skill_3 绑定、Spine3.8.99/FPS30、OnAttack原float32
0.3333333432674408 与10/30的float32编码完全相同，因此得到真实 authored frame10/1⁄3秒。
raw Script base64/hash、mapping、reader/library identity 都封在技能包，旧四位小数帧表只是辅助来源。

原 projectile CAB 直接恢复速度8、onlyCheckHitWhenReachTarget1；Range同GameObject实际
CircleCollider2D半径1.2000000476837158、localScale1。4-1启动范围仅挑一个主目标，
到达后才以 impact target位置为中心动态筛 living enemy，不能给每个启动范围敌人各发一炮。
原始 logic/graphic/movement与碰撞几何随来源 SHA 保存。

Buff模板 JSON 只做离线输入，未导入 V1实现：

- knockback[dir]：START执行Knockback，useSourceDirection=true，未在方向时decreaseForce2。
- rupture：START DamageByDistance(init)，TRIGGER/FINISH实际PURE；到期必须结算尾段。
- trigger_token_skill_within_range：实际TriggerTokenSkillWithinManhattanDistance。
- die_to_kill_token：主人finish时KillTokens，与owned退场清理相符。

## 推力与移动距离：明确可替换的模型 profile

官方 force/weight完整曲线和碰撞未从本地 native body证明。本包通过 AST literal
提取本地历史 `PUSH_FORCE_TABLE` 数据，锁 SHA，**不 import/执行 V1任何函数**。
profile `historical_effect_push_linear_time_projection_v1` 是模型样本，不标 native_curve_verified。

有效等级 = force + source_force_bonus − mass_level，clamp[-3,3]；effect距离表为
0、0.08492、0.37363、1.56247、1.98705、2.77347、3.33058，初速表0、1、2、4、4.5、5.3、5.8。
duration取历史模型2d/v0，再由当前V2分 tick 线性投影；不是宣称复刻官方减速度。
source_facing方向、质量字段和完整rule可由内容替换，无任何内核温蒂ID分支。
背向源减力2、飞行推移资格、坑洞/碰撞与 native DamageByDistance.MAX_DISTANCE4 的用途仍 pending。

实际移动写入累计路径 ledger。walking、forced以及声明的直接位移均只记已接受的真实距离；
墙裁剪、blocked、不动目标不会按名义距离收费。往返回同一点也累计路径，不把净位移0误作没走路。
lease开始记录cursor，不回算之前路程；每0.066秒（本模型30Hz量化2ticks）结算delta×1200/dist1，
refresh/extend/移除/到期先flush尾段并更新cursor，防丢失或双计。真伤走纯计算图与真实HP资源。

Host/Cannon rupture原始overrideKey同为rupture、overrideType3；dump枚举3=EXTEND、maxStackCnt1。
本模型同一definition/target，不双倍2400每格；EXTEND旧到期+8秒，incoming source替换。
原生EXTEND source归属/时长交互尚须客户端校准，不能把这项可替换策略当已证明官方算法。

## 水炮依赖与真实联动

水炮用标准token E2关键帧level1→90的479→585 ATK，在声明same-owner E2/70与half-away模型下得到561。
favor关键帧明确全部0，未把缺失 favor 当0；owner成长继承与客户端取整仍标未校准。
20秒寿命、最多1个、cost5来自E2 talent描述/cnt及token标准属性；本地缺独立token prefab的寿命字段。
原token charpack/普通动画在当前缓存缺失，**没有造每2.4秒普攻帧**，也不用独立干员Mon3tr替代它。

生成用battle DP成本5和on_start owned spawn，在同一outer atomic中提交：不足DP、超过1个或初始化失败
均回滚支付、实体/调度/事件。owner是runtimeID关系，不用名字相等猜归属。
宿主S3 on_start触发其曼哈顿≤4范围内自己的living水炮cost0 S3；别人的/范围外的水炮不联动。
水炮force_bonus=1使同一可替换profile读取force3+1。token自己的Skill动画事件尚未恢复，
linked发射时间采用明确的立即触发模型，metadata保存 timing boundary，不能冒称原生0帧。

主人 initial Aura→owned_nearby token child 每3秒给source主人1SP；离开4格、寿命到期、owner退场取消member。
`respect_recovery_freeze=true` 防外部SP绕过宿主等待projectile-invalid的施放冻结。
S3 cast只等一发弹道的actual completion/invalid，不被8秒rupture延长；命中后可恢复自然SP。

## 实际见证与复核

15项测试覆盖build/真实固定stats/source closure、13周期SP与支付拒绝、等待弹道而非8秒channel、
一发撞击中心splash、force/weight可替换profile、墙裁剪、stationary/zero-force、
实际往返路径与walking起始cursor、尾段/EXTEND不双计、battle DP与max_owned原子失败、
水炮自己的561ATK/强化力/0成本、owner/Manhattan资格、每3秒SP/冻结/20秒/退场、checkpoint/input replay。

独立owner alias退场反例发现原Lifecycle比较owner整数与传入字符串，漏清owned水炮；
root已canonical resolve修复，测试保留alias调用，不用整数绕过。
frame agent成果另只读独立16tests+builder check通过，错误version、EOF、raw payload hash、
精确frame snap、不修改installed/shared reader与不存在alias不fallback均核查。
