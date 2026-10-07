# 第六章原生配置与固定12人目标独立审计

固定 catalog 选择内部 `main_06-14/main_06-15`，显示为 **6-16/6-17**。审计只消费冻结来源与8fa接口源码，没有创建运行模块、修改内核或启动整关。完整原波次、路线、选项、预定义实例、故事原文及来源哈希见 audit.json。

| 原生事实 | 6-16 / internal06-14 | 6-17 / internal06-15 |
|---|---|---|
| 敌人出生 / 精确变体 | 50 / 8 | 1 / 1 |
| 部署槽位 | 9 | 0 |
| 基地生命 | 3 | 1 |
| 初始 / 最大 DP | 10 / 99 | 0 / 99 |
| DP恢复间隔 | 1秒 | 9999秒 |
| 训练标记 | false | true |
| 实际隐藏预定义实例 | 两座 trap_010_frosts | Amiya、Swallow、Blaze 三位 E2L25 NPC |
| 波次控制 | DISPLAY_ENEMY_INFO ×1 | STORY ×5，ACTIVATE_PREDEFINED ×3 |
| 活跃路线 | 20条，含16 MOVE、14 WAIT_SECONDS、3 DISAPPEAR、3 APPEAR_AT_POS检查点 | 敌人只使用路线0，另8条 E_NUM 为控制动作原占位路线 |

两关 movementMultiplier 均为0.5。基地生命99999是后续明确运行覆盖；本审计没有改写这些原生值。6-16寒霜装置分支 `frstar_frosts` 保留一个阶段和两条实际激活命令。6-17敌人为独立 `enemy_1510_frstar2_s@0`，HP95000、ATK1200、DEF300、RES50；不能把普通 FrostNova2 的攻击行为按名称复制给它。

## 原生空 alias 的严格映射

三条实际 `ACTIVATE_PREDEFINED.key` 分别为 `char_002_amiya`、`char_017_huang`、`char_367_swllow`。它们与三个原始实例的 `inst.characterKey` 一一对应。原生 `alias=null` 不妨碍将这个已证的命令键作为显式 `registration_key`；保留原 alias 为空，运行时使用原 World ID。索引身份为 stage + characterInsts + 原始数组下标，不能声称 registration_key 是原生 alias。

数据映射必须：非空 alias 使用原 alias；空 alias 仅在实际激活命令 characterKey 匹配且数量严格等于1时绑定。重复同键、未知键和 `$avatar_amiya` 肖像键均拒绝。独立四个数据测试实际通过，既不将 UI 肖像当作战斗 ID，也不按名字取第一个候选。

三个实例均保持 PHASE_2、level25、favor0、potential0、skillIndex=-1、mainSkillLvl1及原始坐标方向。`-1` 表示未选定技能，不能用 Python 负索引选择最后技能。正常攻击及天赋仍需消费精确 NPC 数据。它们不是固定12人的替代定义。

## 公开调用设计

用内容 timeline 的 `effects` 动作执行 `activate_predefined`，保留三条原始延迟1/7/13秒、原所属 wave/fragment 和其余时序字段。该动作唤醒原休眠 ID，不走玩家 deploy、不付 DP、不增部署历史，也不把 native0槽位改成3槽。NPC 定义和激活仍需新源模块与控制组合测试。

五段故事实际包含7条 PopupDialog。可使用现有 logical ControlSystem：每一条 HEADER/PopupDialog/Blocker 先记录完整来源行，每条对话加入 external ack，保留 managed/blockFragment 的等待义务。使用公开 `submit({action:'control_ack', control:<当前真实实例>, step:<当前严格整数>}, at=T+1)` 回应实际 `control.awaiting_ack`，将每次命令保存到公开 replay；不得直接调用私有 controls/lifecycle 方法。

该外部确认协议保留 `is_skippable=false,is_autoable=false`。一帧响应延迟是明确可替换的模型政策，不是已证原生墙钟。`Blocker(fadetime=.3,block=true,a=0)` 的视觉淡入淡出与战斗暂停关系尚未由此来源证明，不能擅自把.3当作战斗延迟或跳过全部故事。完整步骤、输入锁开闭、取消清理、过期/重复 ack、磁盘 CP 与命令 replay 必须由新模块实际验证。

五份原始 payload 都是严格合法 UTF-8，实际源文件偏移与 base64/SHA相等。既有 source.reference 导出的 script 文本乱码，与这些字节不同。此目录另保存正确解码文本，未修改冻结导出。所有 ASCII 指令种类与旧提取结果相同，因此是文本解码缺口，不是故事字节缺失。

## 固定12人与实际部署分别记账

6-16可保留9槽位和固定12 roster，通过撤退轮换争取12种不同干员实际部署；同时在场容量仍以原9为限。记录每人的提交、接受、拒绝、死亡、撤退、重复部署，不能把提交算作部署成功。

6-17可以保持固定12选定 roster，但在原0槽位下实际玩家部署为 **0/12**。另记原生 NPC 激活 **3/3**，不能放进固定12部署分母或把 roster 入选当作战斗参与。应记三项：fixed12_selected=12/12、fixed12_accepted_deployment=0/12、nativeNPCactivation=3/3，并明确原生训练关例外。若总目标要求每关12人均实际部署，该目标与本原生配置无法同时满足；须由目标层明确例外，不能暗增槽位、改 NPC 或跳故事。

## 当前真正消费者缺口

唯一出生动作带 `isUnharmfulAndAlwaysCountAsKilled=true`。现有关卡转换器明确拒绝此特殊标记；8fa timeline 默认把所有 managed 活体加入成员，普通 lifecycle 退出计漏怪、死亡计 enemy kills。尚无已消费的训练特殊波次信用政策。不能在复制时删标记、普通化出生或伪造敌人死亡。

需要分别记录真实出生、真实存活/技能/伤害、原生波次清算信用、战斗击杀及出路生命损失。特殊敌人原 HP95000 必须保留，不能为了波次结束删除它。原生 unharmful/always-count-killed 的确切作用范围，以及 stage finished 时真实 actor 和技能如何终止，均要作为显式可替换政策写入新消费者并验证。

其他待完成项包括：story_frstar2_s 两个强制技能与 PURE NoSourceDamage2000、三位 NPC 的普通攻击/天赋、五段故事/三次激活实际组合、6-16敌人技能及寒霜装置/寒冷冻结、fence/teleport。现有 Cold 作者模块与完整来源提取是局部能力证据，不能签整关。

本报告没有任何 whole-stage 或客户端对照通过声明，也未启动新长程。
