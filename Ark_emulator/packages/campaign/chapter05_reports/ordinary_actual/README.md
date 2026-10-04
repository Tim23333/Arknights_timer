# 第5章普通两种敌人的实际作者证据

原模块 `chapter05_units/ordinary.reference_model.json` 保持原始字节，SHA：
`dda894f38a083eb7f5edb54e051498e68dfd592cf8e4773ad9e582007688919b`。
运行核心M94保持 `cb321a851dc1ccb373477c73a522fc4ca8c35ce8b1c38d18bbee7e1e028358d7`。

|原变体|HP|ATK|DEF|OnAttack|攻击间隔|
|---|---:|---:|---:|---:|---:|
|enemy_1037_lunsbr@0/f32de44dcf74ba64|3200|350|50|12帧|60 ticks|
|enemy_1030_wteeth@0/6886869808ffa02a|5000|500|50|19帧|90 ticks|

18项真实作者测试通过：对DEF100 blocker的实际物理伤害250/400，
部署后源攻击在tick1开始，所以命中为13/20并按60/90tick重复；
部署实际支付7DP，重复部署拒绝且不重复支付；公有能力对DEF50单位造成200伤害，
HP保持3000/4800，既无恢复驱动也无正HP恢复事件；死亡取消inflight攻击，
不复活；撤退关系实际释放且walker继续走；无阻挡路线到出口扣基地life1，
基地从99999→99998，原单位HP保持3200/5000。

`author.evidence.json` 保存每个单位的blocked_damage、dead、route_exit，
共六组独立可重编译probe、实际CP、public replay、完整JSONL及forward/CP/replay观察SHA。
磁盘CP实际读回续跑与从头公有replay都一致。两个fixture中的blocker为明确测试角色，
不替换或抬高原敌人HP；低HP死亡fixture仅用于临界/取消行为测试。

`delivery.pins.json` 记录所有交付文件。作者代码为
`tools/chapter05/ordinary/test_actual.py` 与 `emit_evidence.py`，没有调用Root特殊fixture。
原模块内容未重建。角色getter默认、steering/body collider、动画/FSM与客户端校准
仍属于既有模型边界；本证据不宣称完整关卡或客户端精度。

## 完整来源 join 准备

`chapter05_plans/exact_join.preparation.json` 记录完整跨关8变体。
5-9原生4变体/51births，5-10原生6变体/73births，不能把跨关8误写成5-10有8种。
5-9原始slots8、DP10；5-10 slots9、DP0；两关maxDP99、life3、moveMultiplier.5均保留。
5-9四个可见ballista，5-10十个hidden且具alias ballista；faust_ballis原始7阶段、
10条ACTIVATE_PREDEFINED动作与alias匹配全部保留。

矩阵保留所有原waves/routes/map/blocks/runes/options/predefines/branches，
每个source variant都有候选module/source属性/帧/出生数/路线关联；不存在空subset冒充全关。
候选文件SHA只是一次准备快照，不能替代core兼容检查、独立peer和整关执行。
ballista完整消费者及集成仍pending，矩阵所有whole-stage/client字段保持false。
