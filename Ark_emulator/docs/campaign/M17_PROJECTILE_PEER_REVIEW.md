# M17 independent projectile review

只读复核原冻结 `campaign_m17_projectile_candidate`，core `b964bef82bbc9f6a05cad76740e81030dc9b3d72e82641c3b809d65fb2df875e`，实际导入路径在每报告记录。使用旧实际 package `packages/campaign/chapter01_models/projectile_lifecycle/model.json` SHA `8d416e8c72e1b3524f5bd6201b6216b42a5d14d9bba4129433c73b9ed58f2c44`；没有改作者实现、旧包、旧测试或旧证据。

`tools/experiments/m17_peer/final_review.py` SHA `688df209c198a9eec587526ea3895cc0d0bdfdd07768db4b9bc0124028bef1a6`，fresh coherent13cases全通过。报告 `validation/campaign/m17_peer_final/report.json` SHA `29769cf8bb43006581d08d5ae51f94089577166dcb859a2701235397d5c9b10e`，core、源、包、helper、catalog/preset开始与结束一致。每次真实Compiler输入先写独立fixture文件，再读bytes/hash后decode执行，包括customprovider与六项typed negatives；各完整SHA在report.fixture_inputs。一项NaN负例是明确的非法numeric诊断输入，实际Compiler拒绝，不由记录器替它拒绝。

## 实测端点

| 独立case | 预期与实际 |
|---|---|
| hidden C4 retained point | tick18已发，目标tick30隐藏；tick114按最后位置爆炸，visible邻居受到746，hidden目标不受伤，CP/commands replay相等 |
| C4 hit-time source stats | 外部Director公开命令tick50加ATK100，tick114两packet各926=`(native470+probe100)*1.8-inputDEF100`，CP/replay相等 |
| normal cast/SP claims | 两signal9/23、距离2/speed5：hit21/35与下一cast141/155；attack.accepted仅21/141，SP最终2，不因多发/in-flight/已结束cast重复恢复，旧claim被下一组清理 |
| moving captured identity | 目标tick10从距1变距2，hit21/35始终是captured target；更近未捕获邻居保持HP5000 |
| invalid callback rollback | 真实active projectile与pendingcast1，on_invalid缺resource失败，expiry handler API完整回滚World/状态/计数/任务/RNG/events，pendingcast仍1。API-only，不冒称dispatcher重试或命令回放 |
| typed trajectory output | 合法自定义provider故意漏必需reached，launch立即ValueError并完全回滚，不创建半合法persistent实例或jobs。它是校验负例，未用空handler代替运行 |
| fixed / follow C4 | tick50目标移动col7；114之前不伤、仍等待1；114分别以col4/7为中心，fixed目标HP5000、follow目标4254，邻居两者4254，cast仅结束一次，CP/replay相等 |
| half-open lifetime | 明确fixture life.1s/speed0/disabled碰撞：born9/23，live collision仅10/11/24/25，expire12/26各terminal packet一次。边界terminal hit是明确policy，不把它当live step |
| max-hit dedup | adversarial纯collision同tick返回captured ID两次；各实例只有hit_count1/一个hit target，hits10/24各370，不双结算，customprovider身份锁定CP/replay |
| retired source | source在真实launch9后tick10公共retire(dead)，已发packet21仍结算370，未发第二signal取消；CP/replay相等 |
| callback child/wait group | 主弹114的on_invalid显式新definition创建子弹114，120才结算370；主cast等待该子弹，只在其结束后完成，未退化成即时伤害，CP/replay相等 |
| typed schema/reference | 6个实际在closure中的负例：bool maxhit、非finite life、未知hidden policy、错误motion contract、非bool allow_other_targets、entity冒充projectile reference，均拒绝 |

这些是模型/事件/独立预期/CP/replay证据，不是客户端callbacks证据。Context查询/直接expiry异常是API范围，其余带roundtrip的场景只使用初态与recorded commands。公共stat probe独立 actor解决caster正在等待时不能再启动另一个blocking manual的合法门。

## 原生来源与声明边界

actual Unity读取SimpleProjectile/ParacurveMovement/AttachToTarget的component typetree及精确MonoScript/PPtr，逐项与源reference相等；Asset bytes SHA在读取前核对。另重读W的实际RangedAttack component与sourceDB ATK470。native normal life10/maxHit1/canHitSameTarget0/stopAfterMax1/stopSourceInvalid0，C4 float life3.200000047683716/maxHit1/stopAfterMax0/alwaysHitTraceEnd1都保留。

3.2→96tick是已声明的30Hz float-snap数学profile，不能从其source float声称native同样量化；普通signal9/23作为two-full-packets profile不证明native动画两个signal就必然等于两包全伤；二维homing/swept point/visual height不证明native碰撞或Paracurve方法体；radius2.5作为AoE解释仍未证明原blast shape。这些client/body/FSM/排序/父子transform边界继续保留。

旧8d inherited `profiles.sampling`仍写source ATK at cast、三项model_gaps仍写not_converted，与实际new child at_hit以及已执行的instance expiry/invalid/wait不一致。root与作者已在新 `metadata_corrected` wrapper独立纠正；新model09c06...只是后续输入，本报告不冒称它在本工具已实跑。适用性复用需要完整definitions/rules/provider有效输入证明，不能直接迁移旧program/input identity。

初始失败两类是peer夹具前提错误，均保留旧JSON/source：自W在active C4期间另开blocking manual被正常拒绝；typed negative误改已被fixture隔离移出closure的normal projectile。分别用外部Director与真实normal closure重建后才记录最终通过，未改core或弱化预期。最初expression/graph trajectory尝试被声明policy implementation类型门拒绝，后来用合法provider才真正验证malformed输出拒绝，不列为core缺陷。

本批范围内没有确认新的core阻断。没有full Boss、完整1-11/1-12、native或formal stage receipt；固定12/36目标保持。
