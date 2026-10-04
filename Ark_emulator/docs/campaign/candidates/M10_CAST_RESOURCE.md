# M10 能力精确恢复冻结与资源门中断

独立runtime目录 `unpack_work/campaign_m10_cast_freeze_candidate/ark_sim` 从queue-bounds候选7e24复制；primary f8、共享cadd、queue-bounds来源及root5a目录均未修改。先只读审QUEUE_BOUNDS.patch：清空无活跃任务的heap、超max(64,2×active)按稳定key重建保留allocator；本分支修改前独立bounds3/fork8/kernel46实际57pass/.35秒。

## 内容接口及兼容

资源spec新增 `recovery_freeze_abilities: [exact ability IDs]`，允许空列表。被列出的active cast冻结该资源恢复，无论其activation mode是什么；与旧parameters.freeze_while_cast/freeze_cast_modes按OR组合，空名单不会解除旧冻结。普通automatic_attack没有被一概冻结，陈的所选S1与普通双击可以分别声明。

名单引用进入Compiler闭包，必须kind ability且由此actor实际拥有；scene battle资源无能力不能声明非空名单。缺ID、错kind、foreign ID、dynamic descriptor、重复/非字符串拒绝。初始实体、flat/timeline spawn的组件override按实际merged资源/能力校验，不留实例绕过路径。

显式 `recovery_freeze_rule` 或资源rules.resource.recovery_freeze可绑定新增纯Bool契约，输入owner(entity_snapshot)、resource名、active casts、time、configured_frozen、parameters。没有任何新默认binding。所用rule必须声明metadata.recovery_freeze_authority=final_override，返回值是**最终**冻结决定，允许主动解除旧或能力名单冻结；不是一个偷偷只能增加冻结的OR节点。严格拒绝错contract、无权限声明、非Bool结果。

资源recovery.selector门新增 `interrupt_abilities` 与可选 `interrupt_cast_modes`。两名单同时给出为intersection；空名单明确不取消任何cast。必须同时有selector和interrupt_when_empty=true，名单也需exact本actor拥有，mode只接受现有activation modes。旧未给名单的interrupt_when_empty继续取消全部active casts。

持续、周期、event恢复以及modify_resource respect_recovery_freeze、amount_rule与Buff人才emit快照共同使用同一精确判定。正增益被冻结，主动负变化维持旧语义。普通攻击两hit只恢复一次source攻击时钟，receiver仍按实际packet计数。

## 时序、规则与原子性

默认名单采用runtime active-cast membership，不凭finish_at提前解除。emit发生于finish handler之前时冻结快照已捕获，随后同tick finish不能恢复该次被禁止的人才SP。显式授权rule可自行选择time半开边界，测试在t1解除而membership名单独立仍冻结；这是可替换模型决策，不能当原生正文已恢复。

ctx.calc只调用kernel session.emit(calculation)，不会回到domain.emit/resource snapshots，避免纯冻结规则递归。仅检测到custom freeze rule的program才给domain emit加完整atomic envelope；检测包括FrozenTuple中的实例override。未配置路径不计算新契约、不新增calculation事件，无新默认绑定。

组合反例先改HP、采样RNG、排任务再emit，规则division-by-zero后整个checkpoint完全恢复。另实际红反例发现直接filtered interrupt原先先commit取消cast/tasks，再emit时规则失败会半提交；本分支把interrupt整个动作置于Session.atomic，保持casts/tasks/allocator/resources/events一起回滚。隔离context兼容已局部同步root四处visibility getattr，不整文件覆盖；ResourceSystem支持旧program只有ruleset、无definitions/scenario的IsolatedContext。

## 规范化内容wrapper与来源边界

新 `packages/campaign/mainline_models/level_main_00-10.m10_resource_precision.json` 由build_wrapper生成，只增加两个字段：

- Chen SP recovery_freeze_abilities=['ability/campaign_chen_s1']。
- Kalts SP recovery.interrupt_abilities=['ability/kalts_host_s3']。

独立移除这两个字段后与原m8_roster JSON exact equal，其余unit/stat/skill/traits/geometry/controls/roster定义一项未改。M10_WRAPPER_SOURCE.json保存原包/新包SHA、实际recipe `_allowSpRecoveryWhenAffecting` 路径与原值。Core中没有charID分支；这些ID只在JSON作者wrapper。

原生flag0支持明确采用所选技能恢复冻结的模型，但客户端方法体、技能affecting窗口仍client_pending。没有把该字段单独当成客户端准确性oracle。

Canonical真实输入：陈初始4SP、敌人119tick出生使S1启动、人才120tick；旧配置观测SP1，新声明保持SP0。凯尔希无ownMon、foreign owner Mon3tr初始HP3000为输入伤口；旧资源门40tick零heal，新S3专属门普通治疗实际接受。没有ctx写入伤口/充SP来假装command replay；陈与凯尔希场景均包含真实完整replay，陈cp120恢复一致。

## 验证身份与范围

自有26项加queue/fork/kernel/domain/event/abilities/M6独立review共 **193 passed，13.58秒**。自有用例还覆盖：normal双hit仅SP1、continuous/periodic/event与主动增益、未来cast变化、token expiry仅中断S3/不取消normal、同tickemit/finish、空名单、rule最终override/Bool、递归预算、实例rule atomic、foreign/坏type/无selector/坏mode/错contract/authority，完整CP/replay。

实际新catalog **82 contracts**：primary79+M9 movement.transition/checkpoint_position两项+M10 resource.recovery_freeze一项；不是机械改测试数字。新wrapper实际239 definitions/74 rules。未运行旧5a全套或整关长程，M10后续完整批次由root统一组织。

本批冻结implementation digest `f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e`；源实际hash与补丁独立保存。M10_CANONICAL_PROBES.json锁actual program/runtime与输入源SHA，M10_SOURCE_HASHES.json锁JSON/源码字节。M10_CAST_RESOURCE.patch从7e24独立base导出，包含自己的资源接口以及明确的visibility兼容同步。没有promotion、formal case提升或审批收据。
