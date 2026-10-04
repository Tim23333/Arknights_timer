# 第二章回归与修订顺序

当前所有修改以独立V2候选执行，历史候选、原包和整关运行保持身份。按下面顺序扩大验证范围；测试成功只覆盖对应条件，不把候选绿色视为全部机制完成。

1. 固定模块与来源：五敌原生variant、数值／动作帧／blackboard／Enemy和MoveController字段；所有运行目标的typed state；固定12人配置及真实依赖。关卡实际52出生／7控制、地图cell及管理标记逐项绑定。
2. 最短真实反例：手动沉默解除同帧防御恢复；移出光环子Buff回调撤源时，同一技能后续damage不能保幽灵防御；gazebo完整request不得丢温蒂distance／参数；airdrp typed运动必须被场地钩子读取。
3. 生命周期和边界：出生保护[0,45)、运动/出现/推坑、地面与飞行、环境死亡归属、被移除source/parent、半开Buff到期、源回调重入、失败完整回滚与guard恢复。不把WAIT节点的position当几何位置。
4. 同版本持久化：公开命令、原序磁盘checkpoint续跑和完整回放比较World、任务、RNG、完整事件。公开属性查询会生成计算事件，需要重放相同查询顺序；不能单为比较排除这些事件。
5. 新核心组合：保父分支SHAs，重叠文件明确合并；原断言仅替换候选导入路径，保原字节；新边界和既有领域/空间/技能/生命周期定向回归通过后再运行0-1与自定义850/60基线。
6. 完整关卡：固定操作、99999基地（只改变基地资源）、真实单位HP；记录命令接受/拒绝，允许退场与漏怪；所有出生/终结与managed timeline完成，保存全事件与持久化续跑。终局后的既定操作用正常API记录拒绝，不能悄悄少计。
7. 独立复核来源消费者与机制事件，把已执行的参考规则、缺实现的开发问题和用户后续实机反馈分开。每次数值/时序修订产生新输入和执行身份；旧结果不迁成新版本证明。

现有M44完整175检查与0-1基线通过，仍有M42 source失效重入反例待M45。因此M44整关用于探索；不会签该漏洞条件的中途正确性。2-9初轮16956因airdrp缺typed state停止，源码输入保持；source_closed_v3补齐source steering和typed运动后在85067继续。所有实际运行定位与最终收据见`validation/campaign/m8_running_jobs.json`及`validation/campaign/runthrough/`。

2-10新增M46通用area.members需在以上第2–4步加入九宫格格边界、主目标地面资格／飞行旁伤、重复/越界ID拒绝、实际impact中心和DEF−50%持续5秒的独立预期，然后再合该关其他敌人闭包与源STORY。

启动前可运行`tools/audit_reference_stage_input.py --package <author package> --output <audit>`，只审来源字节锁与enemy/player实体typed motion。真实新输入8来源通过、旧输入精确指出两airdrp缺字段；两项fresh测试还验证改源字节与删源报错。它明确不审批完整语义，不把本检查通过当整关来源/模型验收。domain实体定义仍由Compiler、可配置公式与独立机制场景验证。

后续长程工具v9在真实forward rule失败时也保存partial完整journal、最后实际diagnostic、原运行replay与失败checkpoint，并以独立failure schema返回exit1；不能把缺最终报告当正常完成。真实periodic1/0在tick3的输入测试保存全部输出且进度标failed，另外v7/v8/v9提前终局后的既定命令及保存CP/replay共4checks通过。现有live v6/v7工具身份不变。v8/v9只读路线诊断使用实际spatial.movement.checkpoint/wait_until，旧diagnostic里的空route_cursor不被猜测填值。
