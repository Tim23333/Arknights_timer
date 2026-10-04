# M26 敌人决策与目标资格合并

新候选 `unpack_work/campaign_m26_decision_eligibility_candidate` 以M23 core0258为共同父版本，合入冻结M24敌人决策与M25目标资格。当前core为 `7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe`，86个契约。主目录M12和历史关卡收据继续保持各自身份。

## 合并内容

`tools/candidates/m26/prepare_candidate.py` 检查三个父实现SHA并建立新目录，保存三方输入和原始冲突。`finish_merge.py` 只解决已检查的schema、provider注册、movement入口和catalog四处冲突。目录只包含V2源码和首关加载器所需的一份离线JSON，无V1战斗Python。

核心接线是：`SpatialSystem.eligible` 在纯几何候选计算后调用与实际 `select` 相同的 `qualifies`，再把结果交给行为决策。这样明确不可选中／迷彩的目标不会令敌人停下来等待一次无法选中的攻击。候选查询不排序、不采样、不发事件；实际select保持自身计分、排序和随机流程。两套opt-in规则及独立替换接口都保留。

M24状态机与M25资格仍是明确数学profile。源枚举和字段已核对，原生方法正文、相对侧别、实际触发顺序及客户端比较未闭合，不能宣布实际游戏准确。

## 实际验证

作者测试原文件未修改；`copy_tests.py` 只调整候选目录名称和同目录测试导入，原／副本SHA另存。最终63项通过（15.60秒），含20项M24、39项M25及4项跨模块测试；另70项领域、空间、公开编队、教学费用／容量兼容检查通过（5.08秒）。结果均确认真实导入路径及core起止一致。

跨模块测试通过公开技能施加不可选中或迷彩Buff，证实有效期内不启动攻击、不消耗随机流、继续移动；半开到期边界纯查询不改变checkpoint，下一次实际选中才消耗随机并产生物理20伤害、目标HP80。另一项验证资格计算抛错后，包括已修改HP在内的完整原子状态回滚。

首次测试2失败/61通过，原因是测试直接select产生未记录到公开命令的trace，以及夹具调用不存在的方法。修正查询证据与命令回放边界后第二次1失败/62通过；最终用实际resources.adjust修正夹具，并单项确认回滚后全选复跑。候选实现没有为迁就夹具改动，两个原失败报告均保留。

1-11决策包280定义、1-12决策包277定义、M25资格参考包58定义均实际compile通过；编译不是整关执行。完整0-1/custom基线已真实exit0：11击杀/0漏怪，tick2408结束/end2550，181937事件，检查点恢复/完整命令回放相等；custom850/60与各自回放通过，core和工具/输入起止身份相等。

M24另获11项独立复核通过，M23/M25/M26分别4/2/12项独立边界复核通过。真实源资产重读、实际输入、初态、CP/commands replay及来源锁分别保存。范围内未发现新的实现阻断；这些不是native算法正确性或整关批准。见 [独立接线复核](M26_WIRING_PEER_REVIEW.md)。

## 证据

- `validation/campaign/m26_integration/merge_initial.json`、`merge_resolved.json`：父core、实际合并文件与冲突。
- `test_source_copies.json`：测试原文件／路径调整副本。
- `feature_tests_initial_20261003.json`、`feature_tests_corrected_20261003.json`：原始失败执行。
- `rollback_fixture_final_20261003.json`、`feature_tests_final_20261003.json`：真实最终1项／63项通过。
- `domain_compatibility_20261003.json`：70项兼容。
- `compilations_20261003.json`：编译与core身份。
- `baseline_20261003.json`及identity侧车：完成后记录完整基线。

下一步为独立复核与原始actor状态／selector绑定，建立新内容身份后按基地99999运行完整第1章。正在运行的M23原输入保持冻结，不将其结果迁移为M26通过。
