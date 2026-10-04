# M7 空间实现独立复核

本轮只新增 `tests_v2/test_m7_spatial_review.py` 和本文档，保持M6文件及M7来源提案冻结。
测试使用真实Compiler/Engine/Kernel RNG、生成和移动系统，没有替换handler或注册fake provider。
以下验证可替换模型合同，不证明原生random distribution、seed绑定、steering或客户端轨迹。

## 短测证据

初期新套件21项实际通过，1.76秒。该结果是核心变更期间的短测，不被重标为最终回放证据。
本轮后续增加steering与回放，最终结果及新身份单列在下方。

| 复核点 | 独立实际预期 |
| --- | --- |
| 35-wave抽样预算 | 33条两axis非零、2条zero range，声明skip zero时实际66 samples，35个spawn.position_resolved事件；只消耗review_spawn，没有隐式imp消费。 |
| zero range | sample_zero_range=false消耗0；显式true消耗2；两者出生位置均anchor。预算差异是声明的模型选择。 |
| 单axis与顺序 | 仅row非零消费1；col,row采样顺序与事件axis记录相同，实际位置逐sample匹配signed公式。 |
| 坐标与符号 | 固定sample(.75,.25)、anchor(4,0)、已转换offset(-.1,.25)、range(.3,.2)、row sign-1得到独立预期(4.05,.35)；pure rule不耗RNG。 |
| 边框cell域 | col=-.25出生原值保留并归属cell0，不被clip为0；col=-.51/3.51明确超出4列cell域，生成拒绝，样本回滚、pending_waves1保持，session fail-stop并要求restore有效checkpoint。 |
| 实际create后失败 | HP initial100/capacity10+reject bounds在entity创建后失败；world/alias/ID/资源/事件及RNG全部恢复，没有born别名泄漏。 |
| override | authored expression替换provider公式后位置为(1.25,1)，仍严格按wave声明消耗2samples，说明采样归属Kernel、算法可替换。 |
| 非法sampler | duplicate axes、x/y而非row/col、空stream、整数zero flag、负range均compile拒绝；duplicate provider samples运行拒绝且不耗随机。 |
| 默认与对角路径 | 默认4邻居从(0,0)至(3,3)为6段；显式8邻居为三个对角段，cost3sqrt(2)。 |
| Corner | 单侧cardinal被墙阻断就不能斜穿，两侧皆挡则unreachable；没有只检查目的格来切角。 |
| Weighted最短路 | 5×7障碍fixture有合法6步底部绕路cost2+4sqrt(2)=7.656854；实际选择7步顶部路径cost6+sqrt(2)=7.414214。证明按加权距离，而非最少hop的8邻居BFS。重复调用稳定。 |
| WAIT | 实际WALK到达(1,1)后停驻规定窗口，再向下一MOVE推进；8邻居不能绕过WAIT checkpoint。 |
| FLY | 同一8邻居profile下，FLY对每声明point直线运动，穿过完整墙，31tick位置为31/(30sqrt(2))的两个轴，path只含该段目的point。 |

初版fixture误用了不存在的 `rule/ark_spatial_route` / `spatial.route` 名称，实际公开合同为
`movement.path` 和 `rule/ark_movement_path`，已修正测试设置；未修改内核或放宽移动预期。
短测中没有发现新的实现阻断。

## 来源和模型的区别

M7来源审计确认route flags/range/offset、portal边框格与五个native mover字段；GetSpawnPosition、
RandomVector2、SPFA和steering方法体仍不可见。上述66预算、独立Cartesian样本、halfextent、
signed axes、corner、sqrt(2)与稳定tie均是显式模型选择。
cell整数中心及[-.5,.5)归属区间是V2几何约定，不是native FromVectorPosition方法体证明。
原生steering参数8/10、20/100不能因本套件通过而被称为已实现了真实force公式。

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m7_spatial_review.py -q --tb=short
```

## Steering独立发现与修复

启动/转向使用独立数值预期：speed2、dt.25、response4、max acceleration1，从静止到
velocity(0,.25)、position(0,.0625)；转向时force归一化后delta velocity模长仍为.25，
保持旧方向惯性而不是立刻改向。真实移动中的墙clip将位置裁到.5-epsilon并清velocity；
替换pure rule仍只能到当前waypoint，WAIT及ground blocked均清velocity且实际停驻。

新反例暴露旧provider将 `distance <= norm(step)` 当成无条件到达：origin(0,0)、goal(0,.01)，
response/max都0，旧velocity(-1,0)或(0,-1)时，本应分别积分到(-1/30,0)/(0,-1/30)，
却都被吸附到goal，同时返回的velocity仍保持旧方向。Root修复后，两个负例原预期均通过，
前向velocity(0,1)越过同线goal的正向截断也保留。

新arrival_radius默认0，M7model显式选.05。只有along>0且实际step segment进入capture disk
才捕获，侧向即使已经位于radius内也不吸附。捕获会显式snap至point并返回arrival_captured标记，
这是可替换的模型capture策略；不能当成native reachDistance或steering方法体已恢复。
负radius拒绝。point grid collision保留，native body width/分离力仍未校准。

初期blocked fixture缺少deployable，无法成为真实blocker，已补正确公开声明；没有改变内核
blocking语义或放宽速度清理预期。

## 最终冻结与完整回放

Root确认核心冻结后fresh执行：**31 passed，3.79秒**。
本suite与既有4项steering联合：**35 passed，4.09秒**。
组合场景在第35tick capture checkpoint，再推进100ticks；恢复分支和完整replay都逐snapshot一致，
包括两次真实spawn采样、对角path、steering velocity和WAIT进度。未跳过身份错误或使用旧实现替代。

当前最终 implementation digest：
`9a7f806e19ef010ed3e7f3e9ad30ddeb8d5e69bb5eb17c58c754723b659ec8ee`。
中间64214d4b版本的29项结果只是历史，不混为上述最终身份。

| 最终源码 | SHA256 |
| --- | --- |
| `tests_v2/test_m7_spatial_review.py` | `87f49f1e8412cbb2c1692d96fd249b7a19a6b7d6bf80e4303531b298e91ffce3` |
| `ark_sim/domains/movement.py` | `2146c191d0e61465379b8de1e420585ceb7bf09b2d8e03371e9a9ddd0a890a6f` |
| `ark_sim/domains/spatial.py` | `8527785cc730e606cd8d6f3f90a8607079fe82232fea324492748ae3c5910f8c` |
| `ark_sim/domains/lifecycle.py` | `60cded2e5a589684851285aed23c2c3a8a04934502dd6d3ebd9c5979d459dade` |
| `ark_sim/presets/providers.py` | `fa2366b49dba24d15ef0dd81915ed9968fb0e55b1558b00a86529447db271a12` |

保持formal36案例状态和M6历史证据，不生成审批收据，不将模型检查提升为原生客户端或正式关卡验收。
