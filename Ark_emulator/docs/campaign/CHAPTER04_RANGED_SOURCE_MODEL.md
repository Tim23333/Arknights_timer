# 第四章远程普通单位源模块

`tools/build_chapter04_ranged_units.py` 生成两个可复用模块，分别选用表射程和源Circle半径。主目录M68的作者测试4项通过，报告 `validation/campaign/chapter04_ranged/author_tests.json`。独立peer和完整4-9／4-10关卡尚未完成。

| 精确变体 | 实际源数值／帧 | 已执行验证 |
|---|---|---|
| enemy_1012_dcross@0/871dabb9d97609ca | HP6000、ATK450、DEF200、RES50；远程及Combat OnAttack20；弹道速度10／寿命5；攻击间隔3秒 | DEF157伤害293；远程先发后稳定阻挡下近战切换，共享90tick时钟 |
| enemy_1011_wizard_2@0/f8bc19b1deb6e9ac | HP2400、ATK300、DEF80、RES50；OnAttack19；弹道速度10／寿命10；攻击间隔4秒 | RES20伤害240；真实发射帧、弹道晚于发射命中 |

两个远程伤害场景保存有序检查点并按SHA重载，完整snapshot与从开局replay一致。原AdvancedSelector配置、精确source PPtr、动画、Enemy与MoveController字段保存为metadata；无额外passive、动画driver、延迟出生、恢复或免疫的假设由builder检查。

狙击手的表rangeRadius为2.2，原触发CircleCollider半径为2.0。`table.reference_model.json` 与 `source_circle.reference_model.json` 分别构造，距离2.1的实际选取结果不同。当前点距离、角色体积、原生碰撞绑定与目标优先级比较器仍待核对；不能以任一短测签原生射程完全准确。

狙击手阻挡近战与远程共用actor next_attack；远程activation在存在阻挡关系时拒绝。`behavior.decision`由显式计算图组合blocked关系、combat/ranged资格、在途cast、控制和显隐；没有向标准提供器添加未消费参数，也没有改内核公式。

同tick出生、已经部署同格守卫的源模型中，现有Engine可能在blocking.changed之前启动首次远程攻击。当前测试保留该实际顺序，之后第二次攻击切为近战并验证90tick共享间隔。首次攻击在实际游戏中的同步顺序尚需独立来源或用户反馈；改变夹具不是该顺序的准确性证明。

原夹具缺少真实部署、DP、敌人路线及错误首次近战预期，失败报告保留于验证目录。构建期表达式白名单错误记录也保留，当前实现使用严格Bool/list比较；没有放宽表达式运行时。
