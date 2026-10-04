# 凯尔希S3与Mon3tr来源模型

`tools/build_kalts_skill_recipe.py` 输出 `skills.kalts.json`，状态为 **partially_implemented**。
本包实际运行owned召唤、host/token技能联动、SP、时间衰减、真实伤害及未击杀HP惩罚，
不是只保留SP占位。没有替换成独立干员 `char_4179_monstr`，也没有给token的null skillId制造官方ID。

## 直接恢复的来源

官方固定选技 `skchr_kalts_3`：SP15/初始0、自然回复1、duration20、
attack@atk2.6、attack@def2、attack@hp_ratio0.5。
host天赋tokenKey精确为`token_10002_kalts_mon3tr`。
技能prefab实读onlyAvailableWhenTokenValid1、allowSpRecoveryWhenAffecting0、
switchToState1、writeDurationToAttackBlackboard1；额外sp_cond Buff每约0.1秒检查token。
这些原始charpack字段、host组件和选技均保留在包中。

本轮还直接解码 `../data/anon_textassets/buff_template_data.dat` 的明文BSON，
使用有界、长度/终止符/类型/数组索引严格校验的离线decoder，不执行其中C#类名，不调用V1运行时。
冻结六份相关子文档的原始BSON bytes/base64、hash、原始payload偏移和解析JSON：

- `kalts_s_3[ratio_atk]`：ON_BUFF_TRIGGER是RemainingRatioToAttributeModifier，
  ATK/MULTIPLIER、isInversed=false、endTime0；开始创建no_kill_mark，结束检查marker再PURE MaxHpRatio伤害。
- `kalts_token[finish_kill_mark]`：ON_TARGET_KILLED移除该marker。
- `kalts_s_2_3[sp_cond]`：无有效token时结束S2/S3、ClearSP并创建SP_RECOVER_STOPPED状态。
- `kalts_t_withdraw_token`：host完成/退场时强制WithdrawTokens，不切成死亡状态。
- `kalts_t_1[token_def_down]`及finish：范围外创建DEF FINAL_SCALER0，范围内解除对应派生Buff。

## 固定E2/70的token属性

使用source token自身phases[2]的1/90级端点，统一rational插值和既定half-away整数模型：
HP5177、ATK1345、DEF389、attack interval2秒、block3、cost10、respawn25秒。
favor两个端点全0，未给token套host信赖增量；端点、原始分数和rounding profile均保存。
这仍是明确的未校准属性模型，client_formula_verified=false。

三个token原始技能槽均是null；模型技能ID使用自有`ability/kalts_token_s3_model`命名空间，
metadata只关联host原生技能，token_native_skill_id=null。

## 实际模型行为

- summon源host，支付battle DP10，max_owned1；第二只活体召唤被拒绝，付款和创建一起回滚。
  owned实体在host退场时移除。25秒redeploy和卡片槽刷新保留source参数，尚未在spawn命令强制执行。
- host S3只选自己的存活Mon3tr，required_targets防无token付款；支付15后trigger_ability到该token。
  token S3为auto_only，普通用户不能绕过host直接启动。
- host恢复driver用owned-live selector、empty_value0、约0.1秒检查、interrupt_when_empty。
  没有token不蓄SP，失token清SP并中断host活动；技能期间暂停自然回复。
- token S3开始置mode1和no_kill1，DEF增加200%。host范围的live aura解除def_zero，
  离开重新施加FINAL零乘数，所以范围外DEF0能压过S3的200%增益。
- 时间modifier使用root通用`ark.attributes.time_layers`的linear_remaining。
  model ATK(t)=1345×[1+2.6×remaining_ratio]，在t0为4842、t10为3093.5、t19为1519.85，结束恢复1345。
  来源证明remaining-ratio形式与端点；缺失token原生Buff采样频率，因此当前明确使用连续求值模型。
- 真实伤害probe忽略高DEF/100法抗，读取实际有效ATK。自己的combat.kill清marker，其他角色击杀不清。
- 20秒结束且仍存活、marker未清时，on_remove按source自身有效max_hp进行PURE 50%伤害，
  不按current HP取半。满血5177→2588.5；已伤至4000则4000−2588.5=1411.5。
  模式、marker和属性随结束恢复。
- capture_view/sample时间被保留；延迟at_cast命中保持施放时曲线值，不按后来hit时钟重新衰减。

## 未伪造的攻击动画与完整单位边界

实际检查发现cache中没有token charpack；其chararts CAB只有两个卡面UI Mono，无TextAsset/Spine。
37个battle CAB、458个charpack GameObject扫描也未发现Mon3tr prefab；root另确认原游戏E盘路径不存在。
新增source会触发重新审查，不在旧probe上静默继续使用。

因此攻击必须由显式synthetic attack_signal probe命令触发，**没有编造native首命中帧或自动攻击时钟**。
源表baseAttackTime2秒保留为属性来源，但未用它冒充缺失的animation事件。
HP/曲线/kill/伤害等模型是真的执行，这不等于原生token战斗图形或完整模式已恢复。

仍pending：token原生prefab/动作、host正常治疗优先级与弹道回调、25秒卡片redeploy、
Mon3tr死亡rattle1200真伤/眩晕、host/token中断detach联动、native曲线采样及客户端逐帧/rounding对照。
`require_complete=True`明确拒绝，不生成转换批准或正式主线通过收据。

## 验证

build/--check与V2 validate成功，60定义/40规则。
**19项模型与来源测试全部通过，74.35秒**，覆盖有界BSON、token数值/null槽、
召唤DP/cap回滚、SP无token/失token、异host不可借token、曲线/DEF/纯伤、范围门、
满血与受伤maxHP惩罚、自身/他人击杀区别、历史snapshot/延迟at_cast、owner退场及精确checkpoint/input replay。
最初replay测试的额外诊断selector查询会生成未记录的trace，已换为纯World读身份；
精确比较预期未放宽，随后连续/续跑/回放一致。

```powershell
..\.venv\Scripts\python.exe tools/build_kalts_skill_recipe.py --source-only
..\.venv\Scripts\python.exe tools/build_kalts_skill_recipe.py
..\.venv\Scripts\python.exe tools/build_kalts_skill_recipe.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/skills.kalts.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_kalts_skill_recipe.py -q
```
