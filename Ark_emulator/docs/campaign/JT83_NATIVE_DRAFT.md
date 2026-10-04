# JT8-3 原生关卡草案

V4的视觉联合独立门已完成，冻结
`e9e7a9d77785aca81efeda7ef4aeb454a782c54cb4b3e9c3ca3f8ef80b0bbb1e`。
两个不同公开操作场景验证真实成员／模式1撤销／退场清理，以及同来源Boss的HP0终局mode3成员保持，
磁盘CP和公有head事件完整一致。Root已核对17冻结摘要；这仍是来源字段与视觉生命周期门，
不能替代完整四模式演出和整关。新的整关在E盘 `JT8_3_82db_native_v4/full_v2.json` 同进程执行。

当前最新草案是 `level_main_08-17.native_draft.v4.json`，SHA
`fdfa0bca0f6034602d1f69630b8727db74c864c226e4de3c17ea3150fae1860a`，
实际在联合底座 `82db6a9d…` 编译，含 346 个可达定义。
原生场景与 V3 完全一致；原 335 个非 Boss 定义逐值相同，Boss 仅添加视觉 Buff 所有权。
视觉源 V3 `11f20921…` 的两个原生光环通过真实 Buff 实例维护成员，模式 0/1 清除、
模式 2/3附着与退场清理由独立场景和本版本联合验证继续核对。
首次恢复生效最大 HP 75000、末阶段恢复 0，原始生命与攻击字段保持 50000/770。

生命值覆盖为 `level_main_08-17.native_draft.v4.life99999.v1.json`，SHA
`a13f8eee57bb43e1fa381e584c37eab0eabaef17752cbe36470668a85cd7d588`，
只覆盖基地生命和必要来源标记；十二人操作仍是 `public_plan_v2/commands.json`。
实际八个外部 ACK、CP10 磁盘续跑和驱动恢复、公有重放至 120 帧的两项检查通过 64.99 秒。
完整关卡与完整四模式证明继续，编译、前缀和视觉局部场景均不等同于整关验收。

以下各版本保留其历史身份，不能作为 V4 新版本的通过证明。

当前最新草案是 `level_main_08-17.native_draft.v3.json`，SHA
`8bac031f347e428def20828cd5790adc25101544303941588c578b123dcaaf6a`。
首次恢复政策的独立来源审查已锁入Boss V5内容，V3的336定义／44出生／四波／完整地图、
动作、控制及预定义字段由新只读收据`0ffb4e73…`另行验证，没有迁移旧覆盖包的身份。
首恢复75000已在不同出生／击倒时点的独立场景实际通过，原raw充值参数0.5保留；
第二恢复0的完整最终演出与整关仍待全链验收。

最新版本为 `level_main_08-17.native_draft.v2.json`，SHA
`df99cd64e98eea6bc26f572852e4a756e7589bda3aa6c8f39e3ad41e788c2161`。
它使用默认首次恢复有效最大HP75000的新来源政策，原raw`hpRechargeRatio=.5`字节不变，
不再将充值参数直接解释成最终恢复比例。其336定义、44出生、地图、控制和机关配置保持原生输入，
实际八ACK／CP10-driver/head到120两项通过39.84秒。
新版onlylife覆盖SHA为 `b245cc2c884a23ec6b4a598e9d3c840ba8adf8f826241db65c200cfdc5691979`，
操作在`public_plan_v2`，28条命令SHA仍为`f74bd538…`。
下文v1保持字面恢复参数旧模型的历史，不作为真实恢复量已核验的证明。

关卡包 `packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v1.json`
已在 WaveTrack V4候选 `4bf1cc…` 实际编译，SHA为
`905cbdd790e9ebf84607a60ec8fdbdd60a2bc2f6ee601fae74b60ae8eecf9a18`，含336个可达作者定义。
它保留原生44次出生、四波、九行十五列地图、十个休眠机关、循环七阶段分支、
DP15、9部署槽和基地生命3。四个精确敌人变体及十二人养成保持来源配置。

## 剧情与演出

STORY原文固定为八个PopupDialog和0.3秒Blocker，Header的`is_autoable=false`保留。
运行控制要求八个实际公开确认，不能自动伪造受理记录。确认驱动按观察到等待后下一tick提交，
属于显式模型操作政策；逻辑时钟与客户端视觉暂停的关系仍等待用户对照。

原生17个PLAY_OPERA请求分别使用具体`blast_effect_x/y`序列。
原始官方资源已固定并解码，两个序列只有CameraShake、ColorGrading、GlobalAudio，
没有伤害、Buff、地块、出生或暂停节点。因此每次独立控制在tick0调色、6音效、9镜头震动，
tick90完成，保留全部来源参数与动作／路线身份。镜头随机不消费战斗RNG。
原生全局Opera锁与并发仲裁方法不可得，独立请求政策明确记录，不泛化到其他Opera配置。

控制包 `packages/campaign/chapter08_stage_controls/controls.module.v1.json` SHA为
`aad91ae8effb4fc75b1ea2af80c95aa371d9b3bf20ebf37d931f5477b062f1b5`。
三项作者检查实际通过，包括八个外部ACK、0.3秒完成时刻、AV节点调度与不消费RNG，
各自磁盘检查点续跑／从头重放完全相等。

完整关卡前缀两项实际通过38.52秒，报告
`validation/campaign/chapter08_joint_v4/jt83_source_prefix_author_v1.json`。
真实八次公开确认、剧情中途CP10磁盘恢复与驱动侧记录续跑、head到120的完整状态和事件相等。
这只验证原生输入前缀，不能作为整关通过。

## 十二人输入

`level_main_08-17.native_draft.v1.life99999.v1.json` 仅覆盖基地生命值，SHA为
`6862cd5a531a7147a10d2300511e0110ea9872f6a50cca8bf3e8a00589b479d1`。
公开操作文件在 `scenarios/campaign/chapter08/level_main_08-17/public_plan_v1/commands.json`，
SHA `f74bd538a048fb3d07aabee4d185da1e099ad5b5b52f5e570b6657f6844e897c`。
十二人的28条轮换、技能与召唤操作已按原地图建造类型检查，避开十个机关位置。
只生命值覆盖已通过逐值比较；操作结果和实际十二人部署必须从执行事件读取。

## 剩余门

WaveTrack V4自己的完整回归、基线与独立18项收据分别确认后才推广。
完整Boss四模式仍在双击倒受控场景中执行；来源首恢复0.5与网站100%描述的冲突须核实政策。
视觉光环与全模式来源字段闭包、关卡控制独立复核、全部44次出生至终结账本、
真实全程磁盘恢复及head必须完成，才能登记JT8-3。
主底座仍20e，正式完整过程进度12/36，用户实机反馈另行记账。
