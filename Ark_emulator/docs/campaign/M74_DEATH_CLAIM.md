# M74：真实死亡的单次击杀结算

新候选 `../unpack_work/campaign_m74_death_claim_candidate` 从冻结M61 `499dbf069d920e034ef5c4a93fb92b6b8a1f869ca4cd2a1de024c8c0798f5180` 复制，原M61/M68/primary及所有live输入不修改。新core `74ac865eb120c0fd180e096d1e2cc2928d35c7fa0d981e62e77f1e0dafdd90e7`，仅Lifecycle、Effects、Rebirth三文件改动，不新增计算合同或默认绑定。

原独立反例来自 `validation/campaign/m61_roster_peer/initial_review.json` SHA `0e77b7101b128d0afe405a428bea9cb7b99f9bcc6d9874d2e2e6625123b6b17c` 的最后实际fixture。HP120、Hero ATK200，唯一公开命令t1施放true damage。Boss首次HP0的on_begin执行self InstantKill skip=True，真正退出并先发Boss→Boss combat.kill；原外层was_alive检查随后又发Hero→Boss。World kills1但事件2，可能重复触发击杀奖励。旧输入、完整events、program/runtime、CP及commands均保存，没有修改期望或删除日志。

Lifecycle在新的真实`dead` transition增加World `runtime.death_generation`；已死重复retire不会增加。新 `claim_combat_kill(ref,payload,cause,generation=...)` 在同一atomic内先写World世代claim，再发事件。claim中保存第一次实际执行者完整payload及cause，来源canonical化、target tags取真实actor；source_policy none不能冒actor来源。Effects和InstantKill共同使用该入口，外层尝试遇到已经认领的同一世代不再发事件。各结算调用保存其预期death generation，新的真实死亡世代不能被旧generation认领。同UID人为重启的直接API测试明确与public replay分开，不将ctx写状态说成公开命令。

本次对原Parent与新Candidate两个独立进程重新执行同一输入：原两kill、新一kill，World各为1；新唯一source是实际inner Boss。`original_parent.json`、`corrected_candidate.json`保完整快照、CP、回放、输入及实际导入路径，不以复用旧fixture expected当实际执行。Public checkpoint在t1前保存，续跑至17，与commands replay完整事件和状态相同。

最终报告 `validation/campaign/m74_death_claim/candidate_final.json` SHA `01b3c7fe94aa61235b002a19af0e4985f27dedb8fda1653e1a9a6b85c6505274`。7项fresh独立测试1.66秒：原反例与public CP/replay、重复retire/伤dead/重复InstantKill/重复claim、普通二阶段最终Hero归属、真世代2与stale1拒绝、sourceNone/origin精确保留、先真实抽RNG再在combat.kill emit的Toggle纯规则中1/0失败导致整HP/claim/kill/events/RNG回滚，以及再次公开伤dead不多奖励。另113项M61/既有domain、controls、abilities兼容10.10秒通过，实际模块路径记录为M74；旧断言没有改。

新增死亡世代及claim是World实际语义字段，会使死亡后的跨版本snapshot不同；不删除这些差异、不称raw等价。原无死亡行为不添加默认None归属字段。`retire(...,damage_attribution=...)` 保留显式M72兼容入口，只有显式给定时按其既有sourceNone entity.died形状输出，默认actor路径不注入None payload。M72的no_source_damage最终kill循环仍需在Root新组合版本改调用同claim，并保完整sourceNone/origin、真实allocation死亡世代；本报告没有声称独立M74已修改该冻结consumer。

本修复为真实模型/API事件一致性，不证明完整霜星、死亡弹道或客户端行为。M70未接线原型已另封为WIP，schema/contract/feature/tests都不冒完成；Root M76 postmortem模块独立，后续合并需新身份和来源/数值/CP重验。client_verified=False，formal_approved=False，无整关收据。
