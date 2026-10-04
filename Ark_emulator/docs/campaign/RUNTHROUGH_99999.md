# 全程执行目标：基地生命值99999

用户已明确：不要求固定12人队伍完美通关，增加的是基地生命值/承受漏怪次数，单位HP保持实际数值。范围仍为第0–17章末两关共36关。

最新用户顺序：先用参考网站及固定数据完成仿真，中途数值按来源核对；完成后用户统一实机核对反馈。缺少客户端输出接口不阻断当前开发，实际客户端验证状态仍单列，不以回放自证实机准确。

`tools/build_campaign_runthrough_input.py` 生成新的输入文件，只改目标life资源initial/capacity为99999，其原始life值另存profile。所有实体、技能、Buff、规则、原始波次/路线/控制/预定义均保持，原包与历史证明不覆盖。

`tools/run_campaign_runthrough.py` 的完成门是：全部预期出生、所有敌人终结、kills+leaks人口守恒、pending0、timeline complete。允许漏怪及队员死亡；不再用zero-leak门证明本目标。保存所有接受/拒绝命令、最终单位资源/位置和生命值、检查点、回放、输入/core/catalog/helper起止哈希。

当前新关卡入口为 `tools/run_campaign_streaming_runthrough_v9.py`：实际decoded输入字节、全部journal、磁盘有序CP/完整回放、终局后既定命令结果、真实movement状态只读诊断，以及forward异常的失败journal/checkpoint都实际测试。版本v2–v8及其历史或live收据保持原字节；各版通过范围见[第二章回归](CHAPTER02_REGRESSION_SEQUENCE.md)与[当前状态](CURRENT_STATUS.md)，不把旧内存CP相等提升成新磁盘续跑通过。

当前继续修订到 `tools/run_campaign_streaming_runthrough_v5.py`：保留actualdecodedbytes、完整events和反应状态，同时使用有序持久化CP及结构化失败报告。v2长程仍保持原字节，不能把内存CP恢复相等重标为磁盘CP验证。独立复核发现/修订版本完整保留，后续最终执行将用已复核的最新入口。

实现已通过独立小场景：原生life1的3只敌人，在新life99999下全程3漏怪、0击杀、life99996，单位HP10未改；CP/回放相等。报告 `validation/campaign/runthrough/profile_tests_20261003.json` 两项通过。

首份真实1-11输入：`packages/campaign/runthrough/level_main_01-11.m23.life99999.json`，SHA `4ae9ec2b10088f3138a8f59754087f4024b175e6899c738971b4b75f822c713c`，父ac0d的life8仍封存。完整试跑正在使用原固定操作脚本；当前只做no-replay探索，后续同一输入需要完整三路与独立审阅。

## 实际准确性

字段覆盖、版本/时间映射和独立比较要求见 [中途数据准确性验收](INTERMEDIATE_ACCURACY.md)。

全程执行、回放相等、客户端/来源一致三种状态分别记录。当前纯字段审计、声明homing/area/relative-side/FSM策略、source旧版本与新表组合不自动证明客户端正确。
当前伤害、技能时钟、状态机、弹道、范围、状态筛选和随机必须完整执行并对照参考来源；原生正文缺失的细节明确规则、可替换参数和待反馈项。未知正文／缺客户端捕获不再单独阻止当前仿真交付；未实现行为或来源／测试不成立仍拒绝完整验收。

基地生命值99999是明确测试配置差异，比较时单列。干员和敌人数值不因便于跑全程而增强、无敌或重置。原生最大生命值、原始强制编队及教学资料仍保留。
当前历史模型验收2/36继续保留原证据；新版99999全程完成数和实际准确性需要新输入、新证据，不迁移旧结果。

## 独立进度登记

`validation/campaign/runthrough/registry.json` 明确登记每个目标的输入、父输入、命令、实现和运行报告。`tools/campaign_runthrough_progress.py` 只消费登记的报告，检查父包与life覆盖、单位/技能/波次未变、输入SHA、运行来源守恒、出生数量和全部公开命令结果。
运行完成、完整CP/回放一致和实际游戏准确性分别计数。当前尚无独立客户端比较器收据，因此准确性始终pending；报告内部即便自称准确也不能提升该状态。
最新进度工具另核对公开命令实际action/time，而非仅命令数量；流式report的完整journal SHA与event数量也验证。10项反例检查通过，读取大journal SHA采用分块，避免进度工具再次复制全文件。
可运行 `..\.venv\Scripts\python.exe tools/campaign_runthrough_progress.py` 生成独立的 `validation/campaign/runthrough/progress.json`；运行未结束时只标running_or_not_reported，不把历史胜利收据迁移到新配置。
