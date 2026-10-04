# M24 declared enemy decision candidate

新ignored candidate从冻结M23 roster0258复制，未改c069/0258/primary。core `c4fc6cb000208e2518c9bf55b742773c1276fc87bdca8241b58a95bd11e80f22`。这批是source-backed声明数学profile和通用内核consumer，不是原生FSM方法体恢复或实际游戏已正确。用户要求基地life99999、单位HP真实、允许漏怪/死亡但完整中间数据实际正确；本批不改life/HP，不为了胜利放宽行为，并继续保留原FSM gap/native_actual_correct=false。

## 源证据

`tools/audit_enemy_fsm_source.py` SHA `8d0f4bec65010d63f9512efc5148812302d984a786b02271f6fe136d66342c3c`；`packages/campaign/chapter01_behavior/source.reference.json` SHA `d5b4c497b6fd7c78b8ba594628549df8b571d947cfba0d70d23d05dcbe7f3ca7`，--check通过。实际重读4个enemy的TT/PPtr/MonoScript，封14个dump class原文、行号/方法signature与5个源bytes锁。

W两mode和mocock两版本均UnitMode._combat==_attack、RangedAttack、SelectorTrigger；trigger min1/keep0/searchTick-1是真字段。Rogue的_attack/trigger都是null PPtr，_combat精确MultiMeleeAttack，selectTargetSource2按真enum是INPUT_TARGET；不能推成无攻击或凭名字猜ranged。Enemy.States真enum MOVE1/ATTACK2/COMBAT3等，独立AttackWrapper与CombatWrapper有不同target/cast/finish方法结构，MoveController有steering8/maxforce10/halfbodywidth0.2。dump方法体空，不能仅凭这些结构声称“native有target必定停移”或完整cast互斥。

## 通用接口

behavior definition opt-in `decision={rule,mode_resource? 或 default_mode,profiles:[{mode,selectors:[{key,selector}],cast_groups:[{key,abilities:[IDs]}],parameters}]}`。rule/selector/ability实际引用进入闭包，actor须拥有castgroup能力；重复mode/key、错误引用、缺失/不合法mode resource/未列mode不fallback。default_mode也必须列于profiles。

纯 `behavior.decision` 输入source/state/mode/casts/castgroups/next_attack/blocked_by/visibility/controls/logicalclock/eligible_ids/profile参数；输出恰好move/attack两个bool，数字bool与额外字段拒绝。规则是可替换expression/graph/provider，无官方enemy ID分支。标准provider的stop_on_target、stop_cast_groups、blocked_target是声明模型，不是native算法。

`SpatialSystem._candidate_input` 是实际select和pure eligible共用的唯一候选field/tag/owner/blocked过滤实现；`eligible` 在geometry provider后、不做score/sort/RNG/emit。`selector.eligibility`纯rule通过ProviderContext.invoke_provider调用实际声明selector provider，custom geometry不被忽略，输入owner/source snapshots与时间允许可替换纯计算。返回身份须来自已过滤候选；limit0没有ready target。Healing与没有显式pure rule的dynamic-limit availability明确failfast，不偷偷简化或读会emit的属性getter。新selector字段eligible_rule提供namespace替换规则，动态引用实际预加载。

Ability.start只对新opt-in决定同步refresh，在真正cast发布/on_start后、普通攻击和movement采样前反映casts；没有opt-in的旧路径不添加决策计算。持续profile在behavior.tick更新World runtime.behavior_decision，Movement与Abilities实际消费它。模式旧C4跨mode存活时，W两个profile的castgroup包含两个mode的normal/C4 IDs，不能因当前mode切换丢掉旧active cast。

M25独立接口qualifies/targeting.eligibility未合入这个M24分支；最终组合由Root三方合并，在geometry后同一资格位置调用。不要将M26已合资格规则当作此版本通过。

## 产物和实测

builder `tools/build_enemy_fsm_profiles.py` SHA `30f1394d300788b443befa5e45f1e9f5855eccb56127425546a05714f6f255ec`，--check过：

- `m24/level_main_01-11.decision.partial.json` SHA `f641e67cf5cd503948f0d590a04579ba632c06d29ab327140cca551cbc042211`，CLI280defs84rules。
- `m24/level_main_01-12.decision.partial.json` SHA `4f1d5166ac835cc1996bdc21b25430a92b1d8a233d0d615ca0b98c2f22d5d4b9`，CLI277defs86rules。

它们保留父M21源/完整scenario及原FSM pending，只为4个有实际模式依赖的enemy绑定声明profile，不新增无关干员。没有完整关卡运行宣称。

fresh20项8.46秒通过；20个实际cases、25个具体输入bytes/hash、程序身份和部分真实事件/最终snapshot在 `validation/campaign/m24/candidate_final.json` SHA `0aa39f4a4c8dbb4903d0724ef076b826aff5ec2d1f81c5306a2b28ee3dd2e768`。helper `verify.py` SHA `1429626bec5d28b3e03834496e56d5649d717ea65525a2e26fa5d350f69f6796`。当前 tests包含有target实际停路/伤害、target离开实际移动、无target移动、cast优先且sameframe自动技能不多走一步、controls半开、blocked INPUT_TARGET不打邻居、能力start刷新失败完整rollback、mode/reference/ownership/输出类型负例、field/customprovider纯读与实际select才消耗RNG、limitzero与dynamiclimit failfast。

实际源definitions的独立数学fixture也实跑：W470/zeroDEF两个selected packets at15/29累计940且不移、无target实际移；mocock有target实际停并cast；rogue通过Spatial.blocking建立关系，blockedcombat开始。它们验证source-profile执行与模型算术，不恢复nativeFSM许可。

205未改兼容项10.13秒通过，报告 `compatibility_final.json` SHA `ba38a4afd8526b466dbd39604a0651d6331705fb2027e6963d6f4486f775127f`。没有opt同输入M23/M24各245events，只排除另存的两个FP字段后全数值/因果/order hash `f2a10d2ff43f4ee87b92192286853e24005178b54697b5a24f19816c4863e551`相等。旧proof身份仍独立，不迁成当前native通过。

完整candidate diff/变动文件SHA在 `validation/campaign/m24/candidate.patch / changed_files.json`。source/core/catalog/preset/helper/产物起终守恒。API setup/异常rollback单列，不把ctx setup当recorded command replay。没有formal receipt。

## 保留缺证

Native Enemy FSM branch顺序、COMBAT/ATTACK切换、target丢失时的刷新与挂起、cast/冷却期间真实移动许可、controller bodywidth/separation、native comparator和客户逐帧仍pending。数学profile passing不能充当用户要求的实际正确；后续需要body/source进一步恢复或客户端独立逐帧证据，不能靠metadata删除这个gap。
