# 同步启动、控制和攻击原型独立复核

2026-10-02，仅只读复核root的on_start、Buff.control、allocations HP计数、普攻来源提取器，
以及攻击线的能天使/陈原型。本轮新增 `tests_v2/test_activation_control_review.py` 与本报告，
没有修改生产源码或攻击线文件，没有通过放宽旧独立预期解决失败。

独立review现为15项；收尾增加满SP AUTO强制启动边界后，与既有activation controls6项及
支持原型10项在同一当前核心下定向重跑，**31/31通过，5.75秒**。
攻击线构建--check成功，其17项测试独立运行通过，42.31秒。
`extract_campaign_attacks.py --check` 对十二份普攻参考数据成功。

## 同步启动与事务

支付不足不施加on_start Buff，整体Session checkpoint保持原值。
支付成功、首个同步effect施加Buff后，第二个资源effect因reject边界失败时，
付款、Buff、cast、cooldown、tasks和events整体回滚，checkpoint精确相等。
同tick攻击采样能看到已同步进入的模式，不依赖一个稍后排队的apply_buff来假装模式已启用。

初次复核查出on_start源资源引用没有编译预检：modify_resource指向不存在的源资源仍可编译，
直到运行才失败。root将activation.on_start纳入既有check_effect，并覆盖source/self两种合法别名；
现在两组独立反例均在编译前拒绝。缺失Buff引用也被依赖闭包预检拒绝。

## 控制与边界

- move/attack/abilities/block控制限制按多个Buff实例叠加；移除第一个Buff实例只释放它的限制，
  第二个实例的attack/abilities限制继续生效。
- 结束时刻采用半开控制边界，达到expires_at时controls不再施加限制，随后callback清理对应实例。
- stun禁止新移动、攻击和技能，并中断施放剩余任务；已在飞的projectile仍按已发射事件落地。
  独立例验证一秒飞行中施加stun，位置保持、没有新发射，但先前弹道在第30tick结算10伤害。
- block=false使原来被阻挡的地面路线单位在阻挡更新后释放，下一步继续移动。
  这不是把blocked_by字段直接伪写为None的测试，而是走实际SpatialSystem.blocking。

## 资源分配伤害计数

三组独立分配：shield charge1/HP0、shield charge1/HP7、shield charge0/HP7。
即使管线返回amount=1234，结算仍按实际目标health资源损失计damage.accepted.amount，
分别是0、7、7；两目标battle.damage_dealt分别是0、14、14。
shield资源支出仍被实际提交，但不冒充HP伤害。
这对应先前支持线报告的allocation汇总缺口，root修复后保持原预期通过。

## 普攻来源和攻击线

十二份attacks.reference行均为source_frozen_not_converted、runnable=false并保留pending。
来源提取器实际读取UnityPy角色root、base mode、attack及局部Mono链接，记录CAB哈希、
effect_frames哈希、config和外部引用。它没有将来源提取标为十二人普攻已执行或已校准；
其他mode、天赋/特性、target filter和source version correspondence仍是明确边界。

攻击线脚本实际核对normalized选技、旧冻结BB/字段、CAB闭包、模式、damage type、
attack event、SP类型/暂停、projectile identity/speed与次数等source guard。
两个包、fixture单位和场景保持partially_implemented，official_unit_config_imported=false、
client_validated=false，不是正式十二人或主线验收。

新增独立首tick检查：

- 能天使初始满SP30时，S3与burst均在tick0开始，mode同步为1；首次launch9、随后11/13/15/17，
  projectile在10/12/14/16/18结算五次100物伤，仅一条attack.accepted。
- 陈初始满SP4时，tick0仅启动S1而不是普通双击，支付后SP0；tick16结算310物伤并施加stun。
  未用普通双击外加第三次伤害冒充下次攻击替换。

AUTO边界已闭合：root新增显式auto_only布尔参数，雷蛇与能天使都在资源已满时拒绝玩家强制启动，
同tick随后由系统自动启动并且只支付一次。独立用例使用雷蛇18SP和能天使30SP，
不是用资源不足假装AUTO拒绝生效；启动cast.automatic实际为true。
两线构建--check均通过，能天使artifact也锁定auto_only=true。

仍保留原型边界：陈prefab预延迟与Spine Skill事件的差异、stun免疫/抗性仍pending；
动画缩放、实际官方养成、天赋、完整target ordering、部署/撤退和客户端对照未被本次通过提升。
这些已声明的缺口不被胜利或回放一致自动覆盖。

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_activation_control_review.py tests_v2/test_activation_controls.py -q
..\.venv\Scripts\python.exe tools/extract_campaign_attacks.py --check
..\.venv\Scripts\python.exe tools/build_attack_skill_recipes.py --check
..\.venv\Scripts\python.exe -m pytest tests_v2/test_attack_skill_recipes.py -q
```
