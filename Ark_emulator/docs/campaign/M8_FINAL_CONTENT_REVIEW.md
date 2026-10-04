# M8 严格输入与 0-11 操作脚本只读复核

2026-10-02，在 root 全回归与 prefix/checkpoint/replay 运行期间进行。此次没有新增/修改测试、源码或内容包；只运行独立进程中的临时输入与现有工具，保存本审查文档。结论属于可执行模型审查，不是客户端准确证明或正式审批。

## 时间轴接口匹配

`timeline_validation.py` 要求显式 policy 与 negative_timeout_policy，校验 count 的整数类型/界限、delay/interval 非负有限数、flags 布尔型，并拒绝 unmanaged spawn 阻塞标志、synchronous effects 托管标志与未知 kind。max wait 只接受 -1 这一负 sentinel，其含义仍依赖显式模型政策。非空 flat waves 与 timeline 互斥；空 flat列表没有额外动作。spawn 递归复用严格 wave 验证，因此直接 route、component spatial route 和 placement 仍经过同样输入门。

`dependencies.references` 仅对 timeline 根记录的 policy 枚举跳过定义引用，未全局跳过 lifecycle policy。动作 spawn 的 definition、nested effect 的 Buff/selector、placement rule 以及以 `_rule` 结尾的 deadline_rule 仍进入实际依赖闭包，payload/metadata 则保持数据而不是意外引用。

capability preflight 遍历 timeline 的 spawn/effects，收集 time.quantize、spawn.position、movement/path/blocking/leak 和 WAIT deadline 计算。正式 0-11 编译实际有两条 movement.wait_deadline 需求，均绑定 rule/ark_wait_deadline。递归规则绑定校验还会拒绝把 movement.wait_deadline 绑定到 time.quantize 等错误 contract；临时反例实际得到 CompileError，未发生规则猜测或默认替换。

Movement 的 checkpoint 1 为到达时刻加等待，2 为 play 时间基准0，3/4 分别要求真实 actor-captured fragment_start/wave_start 非负整数 tick。默认 deadline 图计算 offset=time.quantize(seconds, quantum, ceil)，输出 origin+offset；超过 deadline 即继续，而非再加到达时刻。类型名与整数映射为 MOVE0、WAIT_SECONDS1、WAIT_PLAY2、WAIT_FRAGMENT3、WAIT_WAVE4，与 Timeline 注入的 fragment_start/wave_start 名称一致。Timeline play_start 在 Engine 入口为0；本批没有中途启动另一 play 的输入。

API 仅在 scenario 声明 timeline 时建立 TimelineSystem，注册 handlers 后在 battle/initial actors 建立后 start。Lifecycle 返回真实 spawn ref，retire 同步 canonical 成员释放；完成公式额外要求 timeline phase complete。此前终局取消与旧成员抢占 delay 的真实反例已经由冻结31项 suite验证，此次没有修改它们或重标历史身份。

## 实际发现的通用别名门缺口

临时输入：同一个 timeline 两条 spawn 都声明 `instanceAlias: duplicate`，delay分别0与0.1秒、blocks_wave=false。真实 Compiler 接受，真实 Engine.advance(5) 在第二次出生抛出 `ValueError: Alias already exists: duplicate`。

原因是 timeline schema 分别把每条 spawn 放进单元素临时 scenario 验证，没有聚合跨 action/wave、initialEntities 的全局别名清单。count>1 自动生成的 `/repeat` suffix 与另一个显式别名也需要聚合检查。已将具体反例发送 root；此次不修改冻结源码或测试。该缺口影响非法作者输入的提前拒绝，当前 0-11 实际37个 alias 全部唯一，无此碰撞，不据此否定其现有编译或 prefix 结果。

## 0-11 完整操作脚本

只读核对 `scenarios/campaign/00_11_full_model.json` 的12条命令：六次部署、六次技能，按 tick 非递减排序；六个部署别名、格子均唯一。场景地图8×10、deploy_capacity8、正式 roster12；脚本部署6名，未把“roster12”误称成12名均部署或全部技能执行。

| 单位 | 部署 tick | row,col | native tile/buildable | 朝向 | 已拥有的选技命令 |
|---|---:|---|---|---|---|
| Myrtle | 0 | 6,8 | tile_road / 1 | left | S2，270与1500 |
| Bagpipe | 360 | 6,7 | tile_road / 1 | up | S3，630 |
| Exusiai | 690 | 5,8 | tile_wall / 2 | left | 无手动强制S3，保留自动驱动 |
| Ptilopsis | 1050 | 5,6 | tile_wall / 2 | right | 固定S2模型能力，1470 |
| Saria | 1800 | 4,7 | tile_road / 1 | up | S3，2820 |
| Eyja | 2160 | 2,7 | tile_wall / 2 | down | S3，3000 |

对正式已编译 program 逐项验证：所有命令 ability 都在相应 unit.components.abilities 中，六个手动技能均无 auto_only=true；高台/地面类型分别匹配部署政策。另在独立 Engine 中按脚本顺序使用真实 deployment.prepare 验证整数坐标、cardinal facing、地形、占用、唯一实例和容量，六次均接受；该检查显式 `paid=True` 排除 DP affordability，并且没有推进实际脚本时间，不能当作六次实际支付或技能SP充足的证据。DP、SP、锁卡、敌人清场与动作接受需要实际整关/前缀报告。

新 M8 包实际编译保留37spawn/3effects/3waves，37个出生别名唯一，seed为1995623974。原始 action indices、routes13/14 fragment deadline 与STORY/提示metadata保留；没有删掉37出生中的任何一项。formal_mainline_approved仍false。此审查不将 root 报告的 0-10 35kill探索结果迁移到0-11，不将600tick prefix迁移为整关通过，也没有创建审批收据。
