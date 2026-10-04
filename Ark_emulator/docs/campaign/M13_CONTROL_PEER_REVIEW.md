# M13 通用异步控制独立peer复核

只读开发候选，不修改419b、primary、开发者测试或旧证据。独立工具为`tools/experiments/m13_peer/verify.py`和`fatal_paths.py`。有真实Compiler/Engine/controls/timeline/effects/lifecycle实例及事件；没有空handler、fake模拟器或V1。candidate419b原路径/digest由每次实际import和起止身份检查确认；修订候选需新路径/新输出，不迁移旧通过或失败身份。没有promotion或主线receipt。

## 原419b实际结果

- External ACK真实阻同fragment和后续wave，未生敌pending1；实际ACK完成后恰1出生、credit12，并完整checkpoint/记录commands replay相同。
- 两个control加global同key分别拥有三把锁；一个ACK只解自己，第二ACK后global保持。所有commands留回放。
- 直接API错误control/布尔step/错误step完全不改checkpoint（包含资源/任务/RNG/事件/control状态）。这类直接API失败检查不伪称command replay。
- Pending continue cancel允许以后恰1真出生且不completed；terminal取消保留未出生pending1、不算kill/leak、清control/timeline任务。continue是API-only；terminal来自场景scheduled effect，完整回放通过。
- on_start/on_complete/on_cancel先锁/抽RNG/变credit，再真实表达式1/0失败，完整checkpoint回滚相同。
- 两个同tick即时完成control在完成前已登记membership：两个release事件仍有原blocks_fragment/blocks_wave，最终members空、只生1敌、credit14，CP/replay相同。
- 原生三story×immediate/external共六profile实际逐行参数/原gate flags检查及CP/replay通过。01-11_b五popup在0/120/240/360/480逻辑tick，原Delay总18秒、完成540；01-11_a/01-12原零Delay立即profile为0。external按记录ACK继续；native UI壁钟/NoWait动画/confirmation方法体不假装已恢复。夹具只去除来源action的开始offset，保存明确场景初态，不把该零offset当正式source转换。
- 无control定义的场景没有ctx.controls或controls状态，普通credit+1、出生/波次仍正常，CP/replay通过。

## 保存的真实阻断

1. `Lifecycle.create`在control启用时直接`alias.startswith`，合法None确实可创建；非法整数7抛AttributeError而不是接口ValueError。非法调用前后checkpoint相同，但诊断类型/路径不合法。新的副本应显式检查所有非string，保持null合法。
2. Control.on_start、step、on_complete用真实modify_resource使life=0，在原419b仍执行后续credit+5/emit且control.completed；同tick生命周期随后才defeat。这违反本次要求的stateful control effect终局边界，不是通过ctx手写finished或fake事件制造。三入口分别保存compiled initial state、commands与事件以及CP/replay。修复需经可替换的真实objectives规则判定，terminal取消后不得再标completed、不得后续effects或漏任务。
3. A.on_cancel使life0、B.on_cancel抽RNG/扣credit后1/0的组合，原版没有在取消效果后评估objectives，故B仍running且没发生应有失败；新候选必须使终局触发其他取消，并在B失败时整体回滚到原checkpoint。该直接API事务边界不假称command replay。

旧失败见证：`m13_control_peer_initial.json`、`m13_alias_original419b_peer_frozen.json`、`m13_fatal_paths_original419b.json`、`m13_fatal_paths_original419b_with_immediate_jobs.json`。源profile/nocontrol通过：`m13_control_peer_source_compat_initial.json`。旧419b保持原状。修订候选最终peer结果待另外导出，不以开发者22+202通过替代这些独立期待。

额外源码风险只列待实测：Timeline.action在controls.begin返回后无条件_schedule；如果真实objectives在begin内部已stop timeline，必须确认不会重新排入terminal任务。独立断言检查首tick结束立即无control/timeline pending任务，而非等几tick使漏任务自行消失。

## 修订5fd独立重验

实际candidateRoot为`campaign_m13_control_lifecycle_revised_candidate`，digest `5fd55fa7fd810138c5522e96a2e3842e7a925be58e7ff896392d3b96d5d45e93`。原9个peer顶层case全部通过（source故事包含6个子场景），另fatal三入口/cross-control取消失败/即时membership共5项全部通过。旧419b预期没有放宽，旧candidate/失败JSON没有改写。

追加三项也通过：失败cancel事务后两个合法ACK可继续并完成，credit14、无失败RNG残留，记录commands回放相同；nested emit→random→life0在首draw后停止第二random/剩余children；公开deploy alias7发command.rejected，DP不扣且没有kernel fail-stop或新actor。这是新独立边界，不混入开发者33或compat202计数。

但第四项仍保存真实契约缺口：control步骤使用合法all敌人selector和纯damage graph，在编译成功后因system/battle没有spatial.position抛KeyError。它不是终局修复失效，也不能用假battle位置绕过。`m13_extra_boundaries_revised_peer_actual_failure.json`包含完整fixture package、编译初态/命令、program/runtime与failure checkpoint。首个实验误用了damage.pipeline不允许的expression实现，被正确拒绝；该夹具错误保留在首次extra报告，后改为合法graph才得到真实spatial错误。

all原点问题已交根任务在新的5fd复制副本修复；5fd文件和其报告保持冻结。新预期：全局all无需空间原点即可执行真实纯settlement；首目标健康10与battle life5原子扣减触发defeat，第二目标HP10未动，只有1个damage.accepted、无completed、无终局任务，CP/replay相同。radius/grid在没有明示origin时应编译明确拒绝，不能任意猜battle坐标。修订后另新输出复核，不签promotion receipt。

### 当前文件身份

- `tools/experiments/m13_peer/verify.py`: `6f5b0d98143dcc7ecd8397477e204b1456ff3ed0a47350649d69cd3ce2d64f93`
- `tools/experiments/m13_peer/fatal_paths.py`: `b1abc5d6f2e857a1bfb6b22ed7b84043b2b32a56fca1cc1bee522f717177e25a`
- `tools/experiments/m13_peer/extra_boundaries.py`: `f6f5e892f4dc2cc8c1a596c4ad4b94847044032e4bd4e218927a199978110126`
- `validation/campaign/m13_control_revised_peer.json`: `26211147e4f0d4a74320fefa02f102b14b0e97ed7089e00ba549b8be0f04d2a4`
- `validation/campaign/m13_fatal_paths_revised_peer.json`: `ebfb86f72d965e5f9cb7e0bf64642c9582dd1c4d00d582278dbb43a7fabeb2f3`
- `validation/campaign/m13_extra_boundaries_revised_peer_actual_failure.json`: `14122117c734214bd3ecfea7ea3688a6530555244294008ca643f87d0563dfe1`

## nonspatial最终候选18039b独立结果

candidateRoot `campaign_m13_control_nonspatial_candidate`，digest `18039b0bc51c4aa5946cd41e16316085ac6d81783c70c5c4103667e61e702885`。原peer9、fatal5、extra4、六个context preflight，以及首fatal目标的真实before-damage RNG hook1项全部fresh通过：共25个顶层bounded检查，其中source-story一项含六个实跑子场景。这些不揉入开发者45或compat计数，也不声称全核心/主线批准。

all合法纯graph在没有battle空间坐标时实际结算：首目标HP10及battle life5原子扣减→defeat；第二目标仍alive/HP10、只有1个accepted packet、首tick已无control/timeline jobs，CP/记录commands replay相同。额外在battle施加真实before-damage hook，每packet应抽1个imp sample；首目标终局后实际只有1draw，第二目标不再抽，后续effect不执行。未猜battle坐标。

circle/grid/manhattan在control源没有origin时以control路径明确CompileError；default damage/heal/push缺actor源能力也在编译拒绝。push用合法displacement binding验证的是origin/stat context，不是缺rule的替代拒绝。其最早缺binding的试跑保留为旧preflight artifact。额外RNG试跑曾漏damage.request返回所需effects字段，被正确类型检查拒绝；补完整纯graph合同后实跑通过，不将该夹具错误算核心缺陷。

所有报告记录实际candidate导入路径、起止digest/helper/source SHA；有状态成功场景含实际初态/commands/event ledger与CP/replay。直接API失败/continue取消边界明确API-only；失败取消世界完全不变后真正ACK命令的成功续跑可正常命令回放。没有更改419b/5fd/18039b候选、primary、开发者测试或旧失败JSON。

### 最终独立证据身份

- `validation/campaign/m13_control_nonspatial_peer.json`: `a91443e78610f6aee78ebfdca2592db6dcd93e59d7ff85f005a38a7c1eaf7cf1`
- `validation/campaign/m13_fatal_paths_nonspatial_peer.json`: `81f4dde48aa27da55af2799ad2bb26019bff6db5b0106fa99749a18912be3a5b`
- `validation/campaign/m13_extra_boundaries_nonspatial_peer.json`: `24655e019b092e914ab5058a23828e8946ccdba8f42f7938966ffb32070163e5`
- `validation/campaign/m13_preflight_nonspatial_context_peer.json`: `845f75b46204aed94fc0383f12eb90b586b79ae08732dacf2a074b4000933ccc`
- `validation/campaign/m13_multi_target_rng_nonspatial_peer.json`: `5bb4c296f6e1eb727f8e0c757ff15dd0adb10629693b0a2948b51524c4d6b51e`
- `tools/experiments/m13_peer/verify.py`: `6f5b0d98143dcc7ecd8397477e204b1456ff3ed0a47350649d69cd3ce2d64f93`
- `tools/experiments/m13_peer/fatal_paths.py`: `b1abc5d6f2e857a1bfb6b22ed7b84043b2b32a56fca1cc1bee522f717177e25a`
- `tools/experiments/m13_peer/extra_boundaries.py`: `f6f5e892f4dc2cc8c1a596c4ad4b94847044032e4bd4e218927a199978110126`
- `tools/experiments/m13_peer/preflight.py`: `402e31d33bd68a64c41401f83a2e1a7ff892b504273ba307a0ea0e537952eede`
- `tools/experiments/m13_peer/multi_target_rng.py`: `a25e71a02c1ce37093349a9ebc1ed3177b3fd989f9a04c4e6c163fe1ab74c33e`
