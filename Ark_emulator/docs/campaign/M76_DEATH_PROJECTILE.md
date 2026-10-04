# M76 通用死亡弹道与爆炸源石虫

当前冻结作者候选为 `../unpack_work/campaign_m76_death_projectiles_v7_candidate`，core `67028cc91fe55931a62c19d29c8a04dcc4bc6c354b059b1acaac1982733147ad`。13项作者边界及109项关联测试共122项通过，报告 `validation/campaign/m76_death_projectiles/candidate_final.json`，SHA `8403b90bbe41d09460ba17dd3c103010573487001a4fc0063d49f3b500cba37f`。尚待独立peer、完整基线和4-9关卡组装；主目录保持M68。

`lifecycle.death_projectiles` 是显式数组，每项包含纯Bool `rule`、`parameters`、`projectile_definition` 和源中心 `area` 效果。`lifecycle.death_emission`提供实体、当前typed状态、参数和时钟。规则可以决定沉默或其他机制下是否发射，伤害、范围、弹道和完成政策均可替换。

只有真正 `dead` 转换消费该能力，撤退、漏怪和过期不触发。发射在生命状态关闭前执行，真实源实体和body位置仍有效；发射后弹道自行保留死源与固定anchor位置。World中的 `death_emission_in_progress` 预留防合法同步回调再次退场造成重复发射。回调退场为其他原因时外层重新读取活性，保留内层实际退场原因。资源直接adjust路径在此能力启用时连同HP变化、发射、任务与事件原子回滚；无能力路径保持父协议。

弹道 `completion_blocking: true` 表示声明的在途效果阻止胜利结算，失败终局可直接取消。所有普通弹道默认不阻止胜利；该策略不推断原生所有投射物均如此。模块保留独立的发射、到达、范围结算、命中和无效事件，以及完整调度状态。

爆炸源石虫源模块 `packages/campaign/chapter04_units/bslime.reference_model.json` SHA `3aba5e741cd51df2e5e0bbf02055d4006e050aaeb6e9c258976b46ee4d9650d0`，由 `tools/build_chapter04_bslime_model.py` 构造，源锁为第四章 `3e392d80...`。原BSON `projectile_on_killed` 的ON_OWNER_KILLED先检查SILENCED未设置，再按BUFF_OWNER发射；精确黑板boom.atk_scale4、PHYSICAL／SPLASH／ignoreForSpFalse保留。HP2460、ATK260、普攻OnAttack14帧，死亡弹道无移动组件、寿命1秒、Hit仅reach、Circle半径1.25、地面category1／忽略伪装均有源记录。

实际验证为HP归零tick1发射，tick31爆炸按260×4后减DEF100损940。fly与category4不命中，死亡时SILENCED12拒绝，目标到期前移出范围不命中，最后敌人死亡后等待弹道再胜利，基地生命0先失败并取消，不修改任何单位实际HP配置。真实磁盘有序检查点续跑和从开局回放相等。

范围使用显式纯 `model.area.qualified_radius` 与 `targeting.eligibility`，当前point radius政策不证明Unity实际角色体积重叠；本源动作仍保留其原节点及PPtr。typed默认、真实源dead后ATK取值时点、死亡消息与原生动画等待、杀最后敌后的场景清理顺序仍需来源／用户反馈核对。

原v4同步发射回调再次retire导致两次发射的真实反例保留，v5后预留修复。源targetOptions适配、夹具所有权、direct资源事务、schema调用错误和各中间候选保留历史，不迁移为v7通过。无opt-in实际0-1 tick120及自定义850 tick30完整值对比仅1478条实际program、rule与runtime指纹路径不同，其他类型与float bits相同；新增合同与提供器导致身份变化，完整差异保存，不删除全部同名字段。
