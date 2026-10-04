# 第1章两关的下一执行批次

固定队伍和目标范围不变。1-11有45次出生、1-12有30次出生；源文档/路线/波次/预定义完整保留。
当前 primary 为已验证 M12（`bd60c068...`），第 0 章两关模型已验收；第 1 章的新能力在独立候选中验收。本文件给出实际开发顺序，
不把来源可读、部分攻击或Boss探针当作整关完成。

## 内容组合边界

1. 以 `chapter01_sources/native.reference.json` 的两个原始level建立新的场景wrapper，
   按runtime timeline保留每个wave/fragment/action、count/interval、managed/阻塞标志、控制来源索引。
2. 六种简单近战由 `chapter01_sources/attacks.model.json` 提供；潜行者和两个投掷者由
   `chapter01_models/attacks.model.json` 提供。依metadata的normal/behavior覆盖表替换能力及远程行为，
   保留level instance/spatial/route/rules，避免同名实体冲突或追加第二套普通攻击。
3. W保留旧 `chapter01_models/w/model.json` 来源，并使用新 `w_combat/model.json` 的普通攻击/HP/C4组合子集。
   two-full-packets与first-signal-only两profile均有实际证据；原生发包语义、真正附着投射生命周期/invalid回调
   仍需闭合，不能给完整enemy盖章。
4. 用户指定的12人deck作为显式测试输入；原始characterCards全部保留在source。
   1-11原生隐藏Adnach仍是独立预定义依赖，不能用固定E270队员冒充其E0LV20配置或删除激活动作。
5. 1-12 EMP装置由其真实LV10/skill1/SP5/cost10/stun7来源转换，地图覆盖/保留通行与回收策略应成为
   可复用装置接口。官方2025 token包与2026表版本差异继续列出。

## 通用机制交付顺序

| 依赖 | 当前证据 | 进入整关前下一步 |
|---|---|---|
| wave/fragment与deadline | M8动态timeline，captured fragment/wave origin已实跑 | 原始每个动作及出生守恒，控制阻塞不省略 |
| DISAPPEAR/APPEAR | M9候选47路线断言、0-1同身份恢复/回放通过 | 最终候选合并与全套；1-12实际9对路线加显式policy |
| reachOffset | 候选纯 `movement.checkpoint_position`，坐标符号/墙/边框严格门 | 两关所有非零offset映射与真实路径、到达时点见证 |
| 不可选择/光环/已发射效果 | 候选policy显式区分，hidden保alive/managed membership | 用实际路线和W C4输入证明hidden期间没有提前胜利/误伤/距离DoT |
| 资源冻结与门关闭中断 | 当前按mode/全casts不足以区分某些技能 | M10按ability名单；陈S1阻回能、Kalts门关闭只取消S3并保持普通heal |
| W常攻/弹道/阶段 | 两mode源、9/23事件、技能/模板/投射已封存；部分模型已独立复核 | 独立正常攻击预期、真正C4等待/invalid、phase条件与中断/恢复 |
| 潜行者/投掷者特殊过滤 | 基础攻击26断言已过 | camouflage/target-free与仇恨替代profile边界，不仅复用普通ground selector |
| 教程与预定义 | 原始STORY/Blocker/Delay/PREVIEW/ACTIVATE已恢复 | 明确headless确认与暂停策略，输入锁及隐藏单位激活的负例 |
| EMP | 官方token、skill、MapDependentTrap源已取得 | cost/SP/stun/交互/地图override/退场完整生命周期 |

## 运行与独立复核

每关先做短前缀，保存源、内容、命令、固定配置、实现/规则/RNG身份，检查出生+pending守恒、动作执行和输入合法性。
然后固定脚本跑至完整清场，使用相同输入做检查点、命令回放及事件/任务/资源/随机数比较。
未部署的队员依canonical独立场景补足覆盖，胜利不能替代未触发机制。

只有真实model_gap闭合及独立证据具备后才生成转换review receipt。模型profile与client_pending分开，
源码更新、内容修复或旧失败不会通过改状态字段变成新身份通过。
第 1 章两关仍未运行全程；整体声明模型验收为 2/36，第 1 章为 0/2。当前组装与开场执行见
[场景组装记录](CHAPTER01_STAGE_COMPOSITION.md)。下一批整合已验证通用接口，逐个消除执行缺口。
