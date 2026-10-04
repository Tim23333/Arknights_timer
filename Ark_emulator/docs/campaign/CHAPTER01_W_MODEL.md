# W：可替换模式与 C4 内容模型

本模型基于 `chapter01_sources/native.reference.json` 中 exact `enemy_1504_cqbw` 来源，在冻结 M8 core
`f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263` 上实际执行。
入口为 `tools/build_chapter01_w_model.py`，产物为 `packages/campaign/chapter01_models/w/`。
所有计算、条件、时间和策略均保留在内容定义及元数据中；core 无新增 W/关卡专用分支。

## 源字段与作者策略

来源确认 W 两个 mode、HP10000、ATK470、DEF100、RES50、C4 init9/CD20、倍率1.8/radius2.5。
HP checker min0/max.5、useLTForMax0、toggleOnce0；模式 Buff 的 BSON 切换 mode1/restartFSM，结束恢复默认。
该 Buff 没有直接修改 ATK 的列表，模型因此不会添加攻击增益。

模型选择在 JSON `manifest.metadata.profiles` 中逐项声明：

| 项目 | 本模型执行 | 原生尚未证明的部分 |
|---|---|---|
| HP 模式 | HP 资源变更事件；0<HP<=5000 进入1，HP>5000恢复0 | 比较边界、监听时点及检查器正文；当前固定源配置没有maxHP增益 |
| FSM 重启 | 中断待生效普通攻击、重置 next_attack；已施放 C4 保留 | 原生重启对在途技能、计时器的处理 |
| 冷却 | 命名计时资源，不称原生SP；默认初次9秒、周期20秒，T1进入立即就绪 | EnemySkill 驱动、首次/再次周期、模式恢复重置语义 |
| 目标 | 默认范围2.5内稳定1人，T1稳定3人；施放捕获actor身份 | Default null selector 的继承、原生排序与仇恨 |
| C4 时间 | 1x模型施放.6秒+附着寿命3.2秒，在114tick爆炸 | FROM_ANIMATION缩放、AttachToTarget回调、失效与等待FSM |
| 爆炸 | 目标爆炸时坐标，半径2.5；重叠逐枚结算 | 原生死亡目标/失效/追踪的实际行为 |
| 数值采样 | ATK施放冻结，DEF爆炸时读取；物理1.8倍 | 客户端实际取值时机 |
| 退场 | 已死目标保留爆炸中心，死来源取消待执行cast | 原生 projectile 源/目标生命周期语义 |

以上是可以运行、修改和检验的显式模型选择，不把缺少方法体的字段提升为已恢复算法。
普通攻击两个 OnAttack 事件及抛物线弹道仍未作者，`full_enemy_implemented=false`。
真正的附着 projectile/lifetime/invalid 回调接口仍在 `model_gaps`，对应原生精度在 `client_pending`；
同一个问题可能同时需要通用接口开发和客户端对照，不能只从数组移除来标为完成。

## 实际验证

`builder` 实际生成并执行独立断言：单次C4伤害 `470*1.8-100=746`，tick114生效；
中途 checkpoint 与完整命令 replay 的 state/events/RNG 等快照一致。
半血5000进入mode1、5001恢复mode0，两种模式ATK均470。
三枚隔离炸弹只命中三个所选目标；三个同中心炸弹对每人造成2238，四个目标各余2762HP。
来源退场后没有遗留 C4 伤害。

默认计时资源在 tick0 执行第一份1/30秒恢复。独立时钟计算为270次恢复（含tick0）后tick269就绪，
加114tick后首次impact383，再600tick后impact983。此约定记录在 profile，不能声称已校准客户端9秒边界。

新增 `tests_v2/test_chapter01_w_model.py` 实际 **9 passed / 15.31秒**，它在 M8完整1002项以后新增，
不把数字加成一次未执行的新完整套件。覆盖HP边界、HP死亡、模式恢复、施放后位置/ATK变化、
死亡目标中心、来源死亡、现有C4跨模式变化、重叠伤害与checkpoint/replay。
初次测试暴露了 Boss fixture 缺少 `policy/ark_lifecycle`，现已补齐真实HP退场策略；
两个测试夹具错误（不存在的Buff查询API、资源恢复与passive重置的阶段先后）也分别纠正。

复现：

```powershell
..\.venv\Scripts\python.exe tools/build_chapter01_w_model.py
..\.venv\Scripts\python.exe tools/build_chapter01_w_model.py --check
..\.venv\Scripts\python.exe -m ark_sim validate packages/campaign/chapter01_models/w/probe.json
..\.venv\Scripts\python.exe -m pytest tests_v2/test_chapter01_w_model.py -q
```

1-11/1-12 还需要真实教程控制、预定义单位、route offset与消失/重现。此包没有运行两关全程，
没有签关卡验收收据，正式通过仍为0/36。

## 下一次通用API复查

直接调用 `resources.adjust(alias, ...)` 时，当前 `resource.changed.target` 可保留字符串alias，
按numeric actor ID监听的passive条件会不匹配。上面的机制探针使用resolved整数ref；
常规effect入口已转换ref。此一致性问题需下一次core修改时审查并补回归，
本轮未为了内容探针修改正在执行长程恢复/回放的冻结源码身份。
