# W模式/C4与资源alias候选补丁独立审阅

2026-10-02只读审查 `tools/build_chapter01_w_model.py`、`packages/campaign/chapter01_models/w/`、`CHAPTER01_W_MODEL.md` 和 `docs/campaign/candidates/M9_ALIAS_RESOURCES.patch`。冻结core身份为 `f8b99ec021be6023d5202307574030e074acdbb1ca583ae6ad7775ef7876d263`；没有应用候选补丁，没有修改core、原包或已有测试，也没有发formal approval。

## 实测结果

实际独立运行 root 的W测试 **9 passed in12.47s**；`build_chapter01_w_model.py --check` 也实际通过并输出相同实现身份。另新增独立 `tools/review_chapter01_w_model.py`，直接加载封存probe包，用可回放命令中的fixture能力将HP设5000，保留真实W两模式/C4定义，得到：

| 断言 | 实际结果 |
|---|---|
| HP5000进入T1，无ATK增益 | mode1，base ATK470；每hit746与470×1.8−100一致 |
| T1自动立即就绪并选择三人 | HP命令tick0，真正自动start tick1，捕获3个actor |
| 同中心三炸弹与第四非捕获者 | 12次damage.accepted，每hit746；四人均HP2762 |
| 固定模型时钟 | start1+114，impact115；不是声称native animation/lifetime已校准 |
| 中途checkpoint/restore | 完整snapshot相等 |
| 命令replay | 完整snapshot相等，含事件/RNG/tasks |
| source withdraw | impact前撤退后无遗留伤害 |

证据 `validation/campaign/chapter01_w_independent_review.json` 绑定probe SHA `c658d14c2208e9684be29631497d2d4b375122d5e013d868122f8ca74972bf02`、实际program/runtime和implementation identity。探针构造和结果都明确 `full_boss_approved=false`、`formal_stage_approved=false`。

最初独立探针用直接resource.adjust刺激，再调用attribute calculator观察，造成replay没有该刺激/额外观察trace而失败；随后改为输入内fixture能力+真实命令，读取无副作用base并以746独立结算验证ATK，三路才实际一致。没有删除事件比较或放宽数学期望。直接API修改不是可自动重放的命令记录。

## 源与作者profile边界

source确认native checker min0/max.5/useLTForMax0/toggleOnce0；模式switch/restart buff的attributeModifiers为空，不能虚构低血ATK增加。DB为HP10000/ATK470、C4 init9/CD20、atk_scale1.8/radius2.5。T1 exact selector `m_PathID=-3353799912320919605` 有 `_limitTargetNum=1, _maxNum=3`，而 `_postFilter=4/_abnormalFlag=24` 的实际筛选正文并未由alive+player稳定排序模型恢复。

HP5000 inclusive、5001恢复是显式semantic profile，native比较/检查时点未有方法体；固定HP10000下正确，不是通用HP百分比适配。作者选择active C4跨模式保留、恢复Default重置9秒、计时资源包括tick0、ATK at_cast/DEF at_hit、目标当前坐标爆炸、死目标保留中心、死/撤退source取消，均有明确模型与部分反例。它们不能自动升级为native FSM/callback证据。

`.6+3.2=3.8s` 是以30Hz四舍五入源float32的固定1x模型，当前没有真实AttachToTarget projectile/invalid FSM或原生 FROM_ANIMATION scaling。普通攻击两个事件、抛物线模板尚未作者，W缺少ordinary attack；因此这是可运行的**部分Boss模型**，不能支撑1-11/1-12完整敌闭包验收。源Hash能够标识变更，但builder本身尚未逐字段guard selector maxNum/引用/模式归属；未来源重建建议增加exact linked-pointer及三目标selector guard，不能只靠“两攻击组件数量”为语义审查替代。

## M9_ALIAS_RESOURCES.patch只读接口审查

该候选仅为下一身份补丁。资源部分在adjust和_commit_change前统一 `World.resolve` target/source，使resource.changed与native passive条件使用同一numeric identity；source=None保持None。与现effect入口canonical规则一致，能修复目前直接adjust(alias)使HP监听numeric guard不匹配的已观察问题。在冻结f8本轮没有执行候选，不将本报告记为其测试通过。

schema部分保留system/battle别名，拒空/非string，检查initial和flat waves，并按timeline运行时同样的 `alias/{repeat}` 展开count>1检查静态重复；与 `TimelineSystem.action` 中后缀规则相符。它不能声称覆盖运行时commands/owned动态spawn的全部别名冲突；这类输入仍需World.create冲突拒绝及事务回滚实际证据。未来timeline若增加另一spawn命名策略须同步该验证器。

下一core身份最小验证清单：alias/int两条adjust（包括source alias）产生相同numeric payload与被动HP mode；source=None；未知ref/source提交前拒绝且state/event/tasks不变；initial↔wave↔timeline重复、reserved system/battle、空/非str、count展开重名的CompileError位置；合法重复展开不误拒；effect路径和直接API行为一致；同身份checkpoint/replay。补丁是否适配旧isolated资源helper上下文也应纳入既有compatibility测试。这里未发现静态阻断，不等于未经运行的补丁已批准。

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_chapter01_w_model.py -q
..\.venv\Scripts\python.exe tools/build_chapter01_w_model.py --check
..\.venv\Scripts\python.exe tools/review_chapter01_w_model.py
```
