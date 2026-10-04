# M27存储独立复核与持久化CP工具修订

实际导入冻结 `campaign_m27_event_intern_candidate` core `75fdf7c2ffe99014f707aa900cbe5c4dffc9756229a81b607f0f3ef9178d9b90`。没有改M27、primary、M29/M30、作者测试或live输入；仅新增peer工具与独立报告。

## 存储边界

六个独立正边界通过，另一个已知工具反例被独立重现并分开标记，不能把“7测试绿”解释为durable checkpoint旧工具通过。core/source/contract/preset/helper前后锁相等，两个实际simulation fixture在decode前封字节SHA/seed/初态。

- 原始JSON数字/字符串子类覆写转换函数时，stored payload仍与原JSON encoder数值和字段顺序相等；bool/int/float与signedzero不混，重复alias及跨emit相同immutable payload可共享，原mutable输入后改不污染历史。
- warmcache中的合法子树不使后续非法FrozenMapping/inf或坏cause绕过验证，journal、next ID和pool状态不变。
- 人为强制全部fingerprint相撞，嵌套scalar类型、键顺序和数值仍逐项正确，不以hash相同认定相等。
- 极小cache budget及clear不删历史；事先读取的稳定iterator不受后续emit改变。
- 真实nested atomic同时创建world entity、schedule job、draw RNG及emit causal事件后失败，完整checkpoint恢复，随后ID和cause正确复用。
- 真实能力在tick3/6发同数值operand payload，实际共享immutable payload，CP和完整recorded-command replay相等。共享没有被当安全边界，非法输入继续由公开EventLog验证。

报告 `validation/campaign/m27_roster_peer/final.json` SHA `421232b70bc05cf030fb2a426d22b36cf12e5201cc73a4a9fce8c6cd3ec67456`。本peer不重新测量作者RSS/CPU，也不将作者300tick数据升级整关或实际游戏正确性证据。

## 真实canonical磁盘CP反例

合成actor resources原始执行顺序hp,z(rate1),a(rate2)。tick1存CP，旧write_canonical排序JSON对象，实际文件reload后World resources变hp,a,z。后续原始tick1事件37/43为z→a，恢复为a→z；HP和资源总值相同但完整事件/snapshot不等。未排序的内存CP续跑相等。

这是工具序列化问题，不是75fd interner回归。反例完整fixture、内存CP、canonical保存后CP、原/恢复snapshots保存在durable_counterexample.json，正期望equal=true、实际false没有弱化。canonical value hash可保持排序，durable execution checkpoint则必须保存mapping insertionorder并从实际文件重读证明。

## v3、v4历史失败

Root新ordered writer使v3真实保存CP/reload恢复z,a，原五个input/helper identity门仍通过。但CP第二次读取字节漂移触发ValueError后缺requested final report，仅先前original/journal在，peer报告明确failure durability=false。

v4修复首次/二次CP读取与restore异常：三者checkpoint_equal/durable=false、结构化error、replay独立尝试、最终report保存并exit1。额外completion helper消失仍在after hash comprehension直接抛FileNotFoundError，没有最终失败report，独立保存该反例。v3 source SHA `30e569e193fc0a46ec6754e368a68f544fb7d6375ea06103337a37346acc2fb9`、v4 source SHA `d036226505a3f4a95dbd46827bf59287db6d4cb9bacc5f8ce61bd6e6ed4c97cb`副本及旧报告分别保存在stream_v3/stream_v4目录，没有覆写或重标。

## v5最终九个独立case

实际冻结75fd、同一明确的两leak/life99999 fixture加hp,z,a资源actor。全部输入/helper/core前后真实字节等；变动使用process-local fault/read injection，原仓库文件不改。

1. baseline：实际两leak、life99997，durable CP和完整commands replay相等；从实际保存CP bytes第三方再次Engine.restore，后续资源事件仍z,a、HP/数值/完整journal一致。
2. 旧第二次read换包攻击：identity/pass false，真实decode仍原bytes。
3. actual decode第一次改seed72：package/decoded SHA真实绑定72，末尾盘71拒绝。
4. commands实际decode变更：真实commands SHA绑定新字节，末尾盘旧值拒绝。
5. helper末尾内容变化：identity/pass false。
6. CP第二次load字节漂移：checkpoint/durable false、结构化error、完整failure report和journal保留，exit1。
7. CP初次load字节漂移：同样失败持久化，原sim完整继续，replay独立通过，不把内存CP当durable通过。
8. Engine.restore注入异常：失败phase/type/message保存，checkpoint/durable false，replay独立通过，exit1。
9. completion helper消失：source_at_completion对应项null、source_errors明确，identity/pass false，最终report/journal持久化，exit1。

所有拒绝case没有通过降低gate变绿；peer绿意味着真实拒绝/保存行为满足独立预期。v5报告 `validation/campaign/m27_roster_peer/stream_v5/final.json` SHA `cd7243b44c258c037666524dac3e1ea2247c221461d7c3a997ac1e2faedea305`，实际导入/core/input/commands/helper/source锁及读取次数随case保存。

范围只含immutable存储和证据工具边界，没有正式阶段审批、promotion或native准确性结论。固定12/36、基地life99999、干员/敌人真实HP以及全程实际中间数据正确的要求不变。
