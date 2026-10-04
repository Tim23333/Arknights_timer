# M61 通用延时复活与 InstantKill

冻结候选根 `../unpack_work/campaign_m61_rebirth_candidate`，父为冻结 M58。实际 core `499dbf069d920e034ef5c4a93fb92b6b8a1f869ca4cd2a1de024c8c0798f5180`。primary、M58、M68及旧live输入不修改。新通用域为 `domains/rebirth.py`，其余接线是API、schema/capability/reference/compiler、Lifecycle、Effect及Resource的明确小hunks；补丁在 `validation/campaign/m61_rebirth/candidate.patch`。没有官方敌人ID分支，没有新增计算合同，恢复计算复用显式绑定的纯 `resource.recovery`。

实体可选 `components.rebirth`，必须声明自身health resource、max_count、delay_seconds、restore_ratio、restore_rule，可带retain_buffs、on_begin/on_finish、reset_attack_clock与显式owned ability的reset_cooldowns。资源必须是自身health、初始正值、已有lifecycle policy；restore_rule必须是正确合同，retained IDs必须Buff，CD重置ID必须本actor拥有的ability。定义、有效实例overlay和实际创建都验证。callback effect列表也严格验证，未知字段、bool当数值、错误引用、未拥有ability或非法时间不能编译通过。

首次实际健康资源0时，写World `runtime.rebirth` 的generation/count/waiting/due_at/task/cause，保持同一actor alive以保留managed population，同时active=False、state=rebirth、HP0。中断自己的casts、解除现有阻挡、清理非保留Buff；不创建另一个敌人，不发布第一倒地combat.kill，也不提前释放Timeline member。inactive使移动、攻击、选择、资源恢复停止。retain_buffs按definition配置，owned child清理沿既有Buff规则，不隐式保留全部状态。

恢复任务由World保存ID；phase0 maintenance先于已经预先排好的phase0输入检查due，同时owned callback有严格payload/generation与早到时间门。移除/withdraw/真正死亡或终局即时取消owned job。延时0走同事务同步恢复，不留任务。完成时复算有效资源容量，通过显式纯规则计算恢复值，再实际resource.adjust；正值与bounds必须有效。保持同一runtime ID，配置ATK等on_finish effects，必要时将owned cooldown分别重置为当前tick+量化initial delay，attack clock也可显式重置。默认不重置所有clock，不假称M63部署冷却实现了敌技能冷却。

每个callback及嵌套effect后重新检查generation/phase/alive/终局。私有callback栈仅在call stack内允许生命周期自有effects作用于inactive owner，finally清理，不能通过内容字面castmarker冒充授权。stateful callback使用实际Lifecycle.result结算，nested random的第一个效果耗尽基地生命后，后续credit/emit不继续。on_finish若杀源、开始新一轮generation或使终局成立，旧finish不会写回alive或幽灵completed。所有callback失败回滚World、HP、属性、Buff、jobs、events、RNG及guard；直接Resource.adjust对rebirth路径也从计划开始放在同一atomic，旧无配置路径没有新增transaction分支或系统。

公开效果 `instant_kill` 必须显式event-safe cause及bool skip_rebirth，目标是实际拥有health/lifecycle的actor，不能杀battle或dormant actor。它不调用damage pipeline、不制造超额true damage、不发damage.accepted或受击SP。skip=False可进入配置复活；pending期间重复false请求拒绝。skip=True直接进入最终生命周期，包括已经pending的actor，并取消其任务。HP实际为0，最后一次才有combat.kill及对应source/target/ability/cast/tags；敌方kills是实体计数，不在首次倒地双计。生命周期与调用者source cause保留。

最终 `candidate_final.json` SHA `a54cbf5bb9f081df095bb8841f5b94f62af57eebbbdd17a5412fc34a35adfae3`。32项fresh测试5.23秒，81项旧domain/activation/ability兼容4.89秒。检查包含同ID/HP0/阻挡立即释放/移动和SP暂停、managed wave等待及第二真死人口守恒、第二唯一kill、零延时、早/错generation拒绝、skip true/false、withdraw/终局取消、nested终局不继续、finish杀源/新generation防ghost、真实RNG+1/0回滚与直接resource API回滚、规则/type/实例/owned CD严格门，以及公开CD边界与disk CP/replay。首次managed夹具误查不存在的created_enemies状态键，已改为实际entity.created定义事件计数，原失败日志保留。

来源阶段模型为 `packages/campaign/chapter04_boss/m61/rebirth.reference_model.json` SHA `11f14fa086dc2906bb5318003a9b24880a62d570f4f87aff7a42e0fb40fa0a4b`，constructor实际`--check`成功。exact VID `enemy_1505_frstar@0/9d1e3d01ef79ae3e`，HP25000/ATK420，BB倒地5秒/ATK+.5，选择参考满容量回复后ATK630；serialized recharge .5与参考1.0均保留。公开合成属性探针在tick1造成420、tick152造成630，不能称原生普攻。tick2实际HP0，保持150tick，到152恢复25000；153第二次扣尽HP只计一次最终kill，同actor没有第二出生。ordered CP90→155、完整commands replay与事件全相等。初次测试用有calculation副作用的attributes.value做中途观察，导致额外日志无法由纯命令重现；已改为真实公开合成packet探针，失败日志保留，不弱化事件相等期待。

独立M58/M61无配置捕获108事件：snapshot与checkpoint的全部World、resources、RNG、scheduler、events逐值一致，唯一区别为四个根program/runtime身份，具体双方值写入报告。没有排除任何嵌套trace或数值，不称跨版本raw bytes相等。恢复系统在没有rebirth/instantkill配置时不安装，也不追加World状态或新事件。测试与报告锁全部源码起止SHA，父/候选实际导入路径分别记录。

本包仅转换来源健康/ATK与复活阶段，不绑定空技能假冒完整Boss。普通Attack两个事件的驱动、ArcticBlast/IceShield、地块随机/黑冰、完整技能时钟仍是后续内容依赖；stun/silence/frozen/levitate及初始/复活后睡眠免疫的真实application/control消费者交M70，未把bool放numeric attributes冒充实现。source/reference计划见M60文档与7ad2fb46…来源锁，native method/callback/时钟差异和客户端反馈单列。当前用户参考先行、统一实机后置；client_verified=False，不跑整关、不签formal receipt。
