# 动态波次、截止时钟与可共享trace

持续目标仍为固定十二人与36个标准主线尾关。正式验收保持0/36。
0-10修正脚本的M7探索已完成35次出生、35击杀、零漏怪，12命令全部接受，tick3749终局；
来源输入及旧af961实施身份保存在 `m7_00_10_corrected_full_20261002.*`。
它未执行回放，不因获胜就升级为正式完整模型。新身份长程验收运行于 `m8_00_10_final_20261002.*`。

## 通用调度与等待

新增 `TimelineSystem` 支持声明式wave/fragment/actions，并在World保存阶段、实际起点、动作进度、
托管成员与wake token。relative spawn/effects替代预排的绝对列表；管理成员退场时释放真实门控。
`managed_clear`、`time_only`及负timeout的wait/skip都需显式声明，不能推断为原生-1的唯一含义。
时间轴与flat waves互斥；控制效果同步结束，原生异步UI另留待核对。

Checkpoint 1为到达后等待，2为play time，3/4使用该actor捕获的fragment/wave origin。
`movement.wait_deadline`将截止数值委托给可替换规则，默认通过time.quantize子计算得到offset，
不会把fragment30秒误写成出生后或到达后睡30秒。纯量/冻结Mapping的origins都支持；缺起点编译拒绝。
计算契约总数现79。

真实复核修复了两类调度问题：终局后未来动作继续执行，以及旧成员退场唤醒正在pre/post delay的状态，
从而提前进入下一波。现在终局取消自有任务并保留未生成人数；仅释放真正阻塞当前gate的成员才唤醒。
25项终局阶段、最终31项调度复核与检查点/完整回放均有实际记录，来源详见
[调度实现](M8_TIMELINE.md) 与 [片段源审计](M8_FRAGMENT_WAIT_AUDIT.md)。

## 0-11接入

独立M8组合包 `level_main_00-11.m8.json` 编译240 definitions，保留37出生、六类精确攻击、
STORY1与DISPLAY2，使用运行期捕获origins与显式托管清场策略。
600tick脚本前缀实际通过：六次出生、pending31、三命令接受、零漏怪，
状态处于等待第一波清场；检查点续跑与回放一致。这不是整关胜利证据。
操作脚本六次部署的格子/朝向/所有权已复核；budget与全程技能触发需实际运行检查。

只读最终审查另发现跨timeline动作/重复suffix/initialEntities的alias聚合检查尚需补齐。
当前两个实际包别名唯一，不受影响；该门将在下一次核心变更中收紧，避免在当前长回放中改身份。
见 [内容审查](M8_FINAL_CONTENT_REVIEW.md)。

## 内部trace存储

`compact_trace`采用单次DAG memo与按需复制；EventLog严格JSON验证后复用合法冻结子树，
可变输入独立复制。没有跨emit缓存，不删操作数、不改默认事件payload、顺序、cause或随机样本。
标量子类沿旧JSON编码器底值处理，非法Frozen内容/循环仍拒绝；snapshot仍为plain结构。

新18项与kernel/engine共84项通过。真实30tick与300tick旧/新完整事件hash和state一致；
300tick RSS约358→189MB，保留容器约734570→564051。最后标量边界修订前后的实施身份均如实保留，
不能把prefix减内存结果当完整22GB归因或长程峰值证明。详见 [trace存储](M8_TRACE_STORAGE.md)。

主线验证器改为顺序释放原sim、checkpoint恢复分支和replay分支，避免三份完整历史同时驻留。
动态timeline前缀按实际出生+pending守恒，完整模式检查全部预期出生；不得用缺失动作的胜利代替源转换。

## 当前验证

冻结源码全V2、0-1基线、0-11前缀以及0-10最终长验证分别在 `m8_final_*`、
`m8_00_11_prefix_*`、`m8_00_10_final_*` 记录。运行完成后以exit/passed及同身份比较为准。
原M6/M7失败、成功、探索与性能记录均保留，不重标为新实现结果。
本轮冻结完整测试现已1002项全部通过，591.17秒，见
[完整测试证据](../../validation/campaign/m8_final_tests_20261002.json)。
新身份0-1仍11击杀零漏怪，181,808事件与checkpoint/command replay一致，见
[基线](../../validation/campaign/m8_final_baseline_20261002.json)。
0-10原内容最终长程已经35born/35kills/0leaks，顺序checkpoint与完整replay现已全部相等，
最终 `m8_00_10_final_20261002.json` passed=true；它保留原内容输入，不迁移为后续修订包通过。
0-11原内容完整探索已真实passed：37born/37kills/0leaks、12commands accepted、timeline complete，
tick4319终局/end4400，见 `m8_00_11_full_exploratory_20261002.json`。
该次使用no-replay，checkpoint/replay字段为null，没有升级为正式验收。

随后canonical独立审查发现Saria增伤及Liskam护盾的正式伤害绑定遗漏，已在新内容wrapper修复，
详见 [整合修复及身份](M8_DAMAGE_AND_ROSTER_REPAIRS.md)。Saria版的0-10三路与0-11探索另以新SHA运行；
原关卡结果只证明原包/原脚本范围，不迁移到修订内容，也不证明未部署六人的完整机制。
增伤修订包的0-11全程探索现已真实passed，37击杀零漏怪、12命令接受，checkpoint/replay仍为null，
见 `m8_damage_00_11_exploratory_20261002.json`。修订0-10现已35击杀零漏怪，顺序恢复/回放继续。

第1章新增来源审计、三种攻击模型及W部分模式/C4模型已实际执行独立断言与复核，
见 [攻击模型](CHAPTER01_ATTACK_MODELS.md)、[W模型](CHAPTER01_W_MODEL.md) 与
[W独立复核](CHAPTER01_W_INDEPENDENT_REVIEW.md)。新26攻击/9W测试为冻结全套之后的定向批次。
alias/resource一致性及路线消失/重现/偏移接口在独立M9候选目录开发，primary f8身份保持冻结供长验证。

下一批先收敛0-10同身份全程与回放，执行0-11完整模型与依赖复核；
同时恢复1-11/1-12实际敌人/Boss来源，不把普通敌人的模板套成已实现Boss。
