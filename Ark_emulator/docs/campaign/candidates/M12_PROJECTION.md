# M12 独立候选：标准格投影一致性

新候选 `D:/Arknights/Arknights_timer/unpack_work/campaign_m12_projection_candidate/ark_sim` 从冻结M11 5b逐字节复制。M11、c0、f6bb、primary和原c0证据均未修改。最终implementation为 `bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11`，实际导入路径与运行前后digest均核验。

## 原始反例与实际修复

先读取冻结 `tools/probe_c0_corner_projection.py` 和 `validation/campaign/c0_corner_projection.json`，它们保存canonicalMyrtle的真实普通攻击反例。source(4,4)、target(4.5,5) 的地图cell是(5,5)，标准水平row4 footprint不包含，但旧selector使用Python round得到(4,5)，实际在15刻攻击。target(5.5,5) 两种投影都到6，不攻击。原始证据未重写。

同一个新内容输入分别实际运行冻结5b与M12，保存 `tools/experiments/m12/base.m11.report.json` 和 `candidate.report.json`：

| source / target | 标准half-up预期 | 5b actual attack count | M12 actual |
|---|---|---:|---:|
| (4,4) / (4.5,5) | target row5，排除 | 1 | 0 |
| (4,4) / (5.5,5) | target row6，排除 | 0 | 0 |
| (4.5,4) / (5,5) | source row5，包含 | 0 | 1 |
| (5.5,4) / (6,5) | source row6，包含 | 1 | 1 |

source半格错误排除和target半格错误包含分别实证。每次报告保存实际module path、implementation、program/runtime fingerprint，不能声称跨版本raw日志相等。

## 通用模型选择与范围

新增共享 `project_cell(position)` 使用 `floor(coordinate + .5)`，精确half tie向正无穷：4.5→5、5.5→6、−.5→0、−1.5→−1。它检查有限数值且拒绝bool/NaN/Infinity，只投影，不自行猜地图bounds。

四个新候选文件使用同一函数：

- GridTopology._cell及地图边框；保留原本half-up地图语义。
- 标准selector_grid的source+rotated offset及target格投影。
- Spatial.blocking的current/on-path footprint和direct move边框。
- 编译期空间position验证。

circle/radius的欧氏距离与manhattan连续距离完全保留，不改为cell距离。例子distance.5且radius.5仍包含，radius.499排除。`include_blocked` 自己的阻挡成员例外仍有效，foreign blocker不通过。用户仍可替换完整selector provider，独立custom provider实际让标准footprint外目标攻击通过，证明没有新增不可替换的内核范围硬限制。

未添加新calculation contract或默认rule绑定，无官方ID分支。四方向rotation使用原坐标角度；没有调整内容facing或移动目标来隐藏投影问题。

这是标准模型cell profile，**不是原生连续comparator、body、碰撞或选敌范围方法体校准**。浮点边框/精确half tie和投影顺序待客户端对照；source/native comparator pending保留。原连续region指标和全selector替换权利分开声明。

## 实际运行与回放

21项新独立cases覆盖：source/target4.5、5.5及负half ties，四方向、负margin/upper border、bool/nonfinite拒绝，range/circle区别、own blocked、原canonical反例、block footprint/path、move runtime与compiler一致拒绝、custom provider替换、half-cell route达到portal并实际1 leak。

真实命令场景在初始half-cell范围外，以记录的enemy skill command调用公开move原语到4.4范围内，随后16刻出现一次攻击。没有直接ctx写坐标；完整CP恢复与commands replay snapshot一致。另一half-cell route场景从row2.5投影row3，达到row3.49的tile_end，资源lives3→2、leaks1、实际退场，CP/replay同样一致。

实际own-blocked运行场景另外保存：声明stationary enemy fixture，target(4.5,4)维持cell(5,4)，既有路径可被source(4,4)阻挡。开启显式include_blocked时实际攻击一次，关闭则零次。零移速只是独立fixture配置，未写入生产内容或冒称原生运动参数。

最终日志：

- `final.log`：**172 passed in 33.93s**，包含20个投影新case、M11语义10case副本、既有142兼容case。同实际路径和bd60身份，运行后digest仍相等。
- `own_blocked.log`：另一个独立actual own-blocked case **1 passed in 1.72s**。
- 共173个不同测试case，无失败或skip。两个日志各自保留，未伪称一次173-case命令。

M11复制的10-case测试仅在新目录改candidate路径，不修改旧M11测试/日志。M11独立peer复核4/4已经完成并另存其自己的文件；M12未自行生成审批。

## 内容与审查产物

新 `build_projection_content.py` 对冻结M11 wrapper校验SHA后，只添加投影profile元数据，generate/--check实际通过。产物 `packages/campaign/mainline_models/level_main_00-10.m12_projection.json` SHA：`0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4`。

可审阅patch `docs/campaign/candidates/M12_PROJECTION.patch` 是5b→bd60四文件差异，SHA：`bd61b0b0e9823cc54934e44e717a338cc4340f4df595d251c3f2a205e5bcc2f0`。完整source/artifact SHA矩阵、原c0probe SHA、同输入比较与实际scope保存在 `validation/campaign/m12_projection_candidate.json`。

| 候选文件 | SHA256 |
|---|---|
| domains/spatial.py | `86d0544c1395fffb4af4b8b8cbfc3e82003590502ada66c7e61ce5c9094bc750` |
| domains/movement.py | `b38c55e24d45f017b130dcc54d6f42a61bc6609060801dfafba8e9fb53dcdd8f` |
| presets/providers.py | `5e905ed01fcf72aaba005e3b9b1668427f8a5a7d7e882b186fe964550702ff02` |
| content/spatial_validation.py | `b7020052f4f667d23888fd28732b4c93b1416433b13c72781df1b4cbddcdb8bc` |

bd60源码已冻结。没有执行全关、提升formal36、提交/推送或改主路径。
