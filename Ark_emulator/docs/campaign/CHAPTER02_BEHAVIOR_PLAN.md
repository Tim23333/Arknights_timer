# 第2章末两关敌方源依赖与实现计划

实际catalog选择main_02-09、main_02-10。本任务不改变固定12/36或实际基地life99999要求，不调整干员/敌人HP，不将漏怪当数据错误，也不因模型能运行而声称实际游戏准确。

requirements.reference.json逐variant保存DB原始解析、实际mode/attack/combat/trigger PPtr、属性和动画映射；逐关保存原始waves、使用中的routes、options、runes及25份文件来源锁。关卡2-9有52次wave SPAWN和7次Info，2-10有36次wave SPAWN和Story1/Info1。2-10还必须消费WAIT_CURRENT_FRAGMENT_TIME，而不是固定绝对时钟。

| 依赖 | 源事实 | M26可复用 / 仍缺 |
|---|---|---|
| 9种单模式普通melee | 已有源工具生成exact combat/Spine event模型 | 可复用普通damage/blocked target；native permission、动画缩放仍缺方法体/客户端 |
| yokai | FLY、EmptyAnimatedAbility、attack/trigger NULL、ATK0 | 显式无攻击，使用真实飞行route；不能把empty combat当缺物伤fallback |
| yokai_2 | FLY但combat/attack同MeleeAttack，trigger AdvancedSelector，circle2，f8，ATK220 | radius2 selector + M25资格 + strict decision + physical；禁止blocked_only强塞飞行攻击 |
| defdrn | Empty combat；AuraAbility DEF additive300，CircleRange；DB range_radius2.5、prefab圈1；removeLeave/detach均true；SilenceableTalent | Buff.aura/DEF层/来源退场复用；BB范围加载、silence驱动、selfOption2/TargetValidator语义需明确adapter，方法体缺证不算实际正确 |
| mocock / wizard | ranged + source projectile，mocock f22/speed5、wizard arts f19/speed10 | M17 projectile/at-hit/retired source可复用；精确source capsule/physics、callback与FSM须再绑定 |
| aoemag | arts；waitForAttackEvent0、predelay0.6669999957，PhysicsRange多个BoxCollider；postFilter0/unlimited | 前摇21tick为明确量化profile；不能用f24、radius近似或单体physical代替；Box overlap纯provider需要来源变换定义与独立几何反例 |
| skulsr | 双mode；近战f53、远程f14/17×0.25999999；DEF-.5持续5秒；BB atk+.5；serialized threshold.4 vs DB.5 | Buff属性/5秒半开/资源事件/模式恢复/重启FSM已有；阈值加载矛盾硬源gap，不能猜其中一个；multi-hit projectile宽域/附加buff时间点须证 |

先在独立内容目录开发有原始字段支持的最小依赖：无攻击飞行actor、飞行ranged样式的实际f8攻击、声明BB圆DEF光环、skulsr实际减防Buff。不改M26或primary；无需新官方ID硬编码的内核原语。普通攻击/光环内容仍按来源映射，完整bundle的require_complete必须拒绝尚缺的PhysicsRange、阈值来源和原生body证据。不得删除旧gap或制造普通技能placeholder。

每个新场景独立锁fixture bytes、core/provider/源/helper前后身份；公开probe伤口/移动/撤退能力与commands用于CP/完整回放，不能用ctx手写装成command。检查飞行攻击能打真实范围目标且不要求block；光环进入/离开/重叠source退出的实际结算；减防在tick149有效、tick150消失；invalid/source drift failfast。

第1章45(1-11)/30(1-12)是原生SPAWN actions之和，并不含我方owned召唤、预定义NPC或装置实例。已封敌方serialized component闭包和五个BSON模板未发现非wave创建字段，但native方法体缺失，不能证明任意隐藏方法无召唤。runthrough ledger必须按实际definition、side、ownership、registration和birth cause分组，保持wave敌人守恒与非wave actor分别计数，不能拿World所有出生数与45/30比较。

此计划不签正式收据。新包必须分别列model_gap、source_gap、client_pending；实际方法体/客户端数据未知不会被降低为已正确。
