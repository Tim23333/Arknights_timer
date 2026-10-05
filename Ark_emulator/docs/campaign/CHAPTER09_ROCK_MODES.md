# 岩石敌人模式与路线

新增隔离候选 `ed5ad49acb134bf00b90b758d7cad0e95f4ec20125f70765ed591f90fef58af4`
从完整焚毁者候选2c38分叉，四文件差量保存在 `tools/chapter09_rock_modes_v2/source_delta`。
没有改变当前生产核心，也没有迁移旧整关验收身份。

近地悬浮需要分别表达目标／阻挡运动模式与路线运动模式。
[深池飞行兵参考说明](https://prts.wiki/w/深池飞行兵)明确空中目标仍采用地面寻路。
旧初始化和 `set_motion_mode` 将两者同步，新内容可显式声明 `spatial.route_motion_mode: 0`，
同时保持 `spatial.motion_mode: 1` 与目标motion位2。
公开动作 `set_motion_mode` 可以通过 `parameters.route_motion_mode` 指定路线模式。
没有新声明时继续使用原有同步默认。枚举仅接受严格整数WALK0／FLY1，实体、初始实例、波次及动作分别验证。

路径查询按真实路线模式处理地形，阻挡按当前显式目标运动模式处理。
作者门用实际墙体、部署阻挡者、落地公有命令及完整CP/head验证了地面绕障、空中不被地面阻挡、落地后恢复阻挡。
非法枚举和布尔伪值均拒绝，失败不修改状态。

源消费者增加两项正式能力：

- 深池飞行兵的 RecoverAnim 只在行走模式且未被阻挡时触发一次，28帧Change占用保留，
  当前V2控制与优先级参考下，tick2落地状态事件加0.5秒控制后于18开始、46结束。
  未解除阻挡时不会触发，解除后实际施放；切模式会取消旧攻击及重置明确能力时钟。
- 守墓石像石化10秒后启动真正的 Born2Fly/Start 能力，20帧动作占用保留。
  源OnStart事件在20帧添加empty模板的 `dugago_reborn` 标记；视觉石化healing Buff没有虚构HP恢复。
  当前mode和运动在源activeBuff起始时切换，完整动作结束前不进行普通攻击。

来源与当前参考存在差异，模块明确提供两个profile：`native_literal`保留20%复生与WALK字面路径解释；
`prts_reference`采用100%复生和空中目标资格，同时仍走地面路线。
四份JSON分别位于 `packages/campaign/chapter09_consumers/rock_modes_v2`。
旧same-hit来源柱体trait判定继续保留；固定BSON的临时mark create/clear与PRTS描述的1秒破碎效果
需要另一个明确消费者政策，尚未合并成全敌人完成声明。

冻结作者证据共8组：3个通用路线／非法输入门和5个真实模式场景，6个CPP/head严格全字段相等。
冻结收据见 [freeze.v2.json](../../validation/campaign/chapter09_rock_modes_v2/freeze.v2.json)。
独立数值与路线复核、当前核心完整回归／基线、客户端Collider和技能启动对应关系仍待验收。
已完成原始捕获保存精简收据后清理，不保留大日志。
