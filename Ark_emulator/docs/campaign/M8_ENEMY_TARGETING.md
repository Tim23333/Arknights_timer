# 敌方排序的嘲讽绑定

canonical Nightingale见证发现，Bird基础taunt_level1虽由真实token来源恢复，正式敌方score仍仅按距离。
旧support测试临时为合成敌人绑定 `rule/support_taunt_score`，没有证明生产整合包已使用它。
因此Bird较远时会选更近普通player；旧失败另由独立见证保留。

`tools/build_m8_enemy_targeting.py` 在roster修订包上生成新targeting wrapper。
将来源封存的score profile复制为 `rule/m8_enemy_taunt_score`，只绑定实际敌方定义；
玩家攻击和治疗的单位局部规则保持原样。导入未来敌人时，作者必须使用这份profile或显式替代native variant score。

该显式数学profile为被阻挡权重1e6、基础taunt权重1e5，随后距离和稳定actorID。
它与原生仇恨算法不是同义词：原生排序/例外、动态taunt modifier的有效属性读取仍列gap，
数值权重可在内容规则中自定义，不加入任何Night/Bird的核心分支。

`test_m8_enemy_targeting.py`实际3passed/.60秒，使用生产敌人定义上的真实score绑定：
原包选择距1的普通player，新包选择距2的Bird；声明的阻挡优先仍有效，Bird退场后重新选择；
核对只有enemy定义取得该绑定。`--check`与两个主线wrapper实际Compiler均通过。
独立Night见证使用修订输入继续核对，完成后保存其确切输入/源/实现和命令身份。

这三项是当前M9全套启动后新增内容测试，不属于该次已收集套件。
targeting wrapper没有覆盖roster旧输入和21条已冻结机制见证，没有重写原关卡长程结果。
正式关卡与完整原生干员状态不变。

## 独立复核后的阻挡方向修订

原score来自player侧选择blocked enemy，条件是candidate.runtime.blocked_by==source.id。
在enemy侧选择player blocker时方向相反，独立真实WALK/部署场景发现仍选Bird，不能把原人工反向状态测试当作完整证明。
新 `build_m8_enemy_targeting_v2.py` 保留原包并生成 `*.m8_targeting_v2.json`，只修为
source.runtime.blocked_by==candidate.id，来源/输入SHA及修订元数据另保存。

新4项实际passed/.74秒，增加生产gopro+WALK路线+deployed player、真实blocking建立关系，
同时复核Bird优先、blocker优先和退场。下一M10综合内容以v2为输入；独立原失败场景继续复核。
动态taunt与原生完整仇恨仍在gap列表，未删除。
