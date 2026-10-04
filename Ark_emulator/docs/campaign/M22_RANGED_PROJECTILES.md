# 第1章普通远程投射物

本批仅新增内容和独立场景，不改变正在全量验证的M21 core `c069e020...`。
`tools/build_chapter01_ranged_projectiles.py` 以M21两关包为父输入，将实际mocock两variant及安德切尔弩箭绑定到同一个通用持续投射物接口。

生成器实际重新读取projectiles CAB中的SimpleProjectile和ParacurveMovement/AdvancedMovement完整Typetree，与源参考逐字典比较。Simple字段lifetime/maxHit/重复命中/stopAfterMax/sourceInvalid/endHit逐项核对；mocock使用速度5、visual raiseHeight.5、threshold1.2999999523162842、lifetime10；crossbow使用AdvancedMovement moveType1、速度10、无动态速度/惯性、lifetime5。两者采用声明的逐刻平面homing、relative swept trace point、捕获ID不改选、活目标一次命中模型；原生三维轨迹/碰撞和cast-end清理方法体仍client_pending。

三条实际普攻移除旧固定飞行时间参数，使用 `projectile/chapter01/mocock` 或 `projectile/chapter01/crossbow`，source/target属性在hit读取。源普通攻击信号22/9刻和属性、选择器、技能引用保持；旧profile的固定launch distance文字在新包内替换为真实persistent profile，没有覆盖旧包。

## 当前证明

- 1-11新M22输入278个定义编译通过，SHA `ad147b19e709d6dbd0f935c6a4aeb80e5f8dddad744af4ad0829f583cb8dc262`。
- 1-12新M22输入274个定义编译通过，SHA `a681a1d4fc76e613f658ea3a27fad4cd0ecd0923308f366b2dafe568af9f30ce`。
- `tools/experiments/m22/test_ranged.py` 2项实际通过（2.87秒），运行同c069候选，core开始/结束相等。
- 使用真实mocock能力，合成目标在第23刻通过公开命令移动并产生更近诱饵；第28刻前不结算旧固定距离包，之后仅原捕获目标受伤，诱饵HP1000，单实例quota1且无残留owned jobs，CP和完整命令回放状态/事件相等。
- 使用真实E0L20弩箭，9刻launch、10刻由独立Director加100ATK、12刻结算 `(199+100)-30=269`，目标HP731；CP和回放状态/事件相等。

两项是明确的独立actor场景，普通攻击改成手动只用于隔离一次发射，原选技与冻结引用仍保留。初次诱饵错误地拥有产生自身的移动能力造成引用循环，第二次错误移除NPC所选技能导致冻结引用不闭合；失败记录保留，修正fixture后未改变候选。

新的追踪内容仍待另一agent独立复核；整关胜利、enemy target-free/abnormal过滤、移动攻击FSM、教学编队与来源/整关收据继续列为未完成，不增加2/36进度。

原始完整1-11 M22场景另已实际跑至805刻：敌方出生2+pending43=45、0击杀/0漏怪，89刻检查点续跑与从头空命令回放相等，70067事件严格比较。原控制、NPC/预定义、波次和路线均未截断；这仍是前缀，未部署固定队伍或完成清场。报告 `validation/campaign/m22_ranged/01_11_prefix_20261003.json`。
