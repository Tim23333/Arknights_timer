# M49 独立来源与可见性消费者复核

冻结候选根 `../unpack_work/campaign_m49_visibility_candidate`，实际起止 core 均为 `e6d05494938ef71a20091b287475fc3e297b9831366a030b349b319a7df515a4`。作者源码、旧来源和模型没有修改。本次独立夹具、工具及证据位于 `tools/experiments/m49_peer`、`validation/campaign/m49_peer`。

最终独立报告 `final_review.json` SHA `e7e0c7c7235d579e3c6952e99dcf5b30f484000d479de068fd0a1a2ea5cf9afb`。17 项实际执行测试由9项新通用夹具和8项新来源消费者组成，未调用作者 fixture。任意单位名称、target-role 自定义事件、资源驱动 held 规则证明接口没有官方 ID 或固定事件分支；可配置 .2 秒 deadline、后续 pulse 重置、held 到实际 release 才开始恢复、多个 parent 各自 child、半开 immunity 与永久底层状态、父提前到期、真实 child on_remove 抽 RNG 后规则抛错的完整原子回滚均通过。pure eligible 查询前后完整 checkpoint 相等，未新增事件或随机数。

来源复核重新使用 NativeAssets 读取原始 Unity typetree，通过 exact prefab `_checker` PPtr 找到三个实际 checker，全部 raw components 与冻结 source closure 相等。Lurker `_disableWhenAttack=1`，jshoot/jmage 为0；三者 blocked1、restore3、INVISIBLE9。后两者普通射击不揭露；新的观察者 DEF80/RES40，实际 jshoot frame16 发射、tick19 物理180，jm age frame19 发射、tick22 法术210，随后的公开射击命令因目标仍不可选而拒绝。Lurker 实际路线上由可阻挡实体建立关系，frame13 物理220，controller last_pulse13；公开命令14退出 blocker，104恢复隐身。初次该夹具漏写 deployable，因未形成真实阻挡而没有伤害；其日志保留，修正真实阻挡配置后才计成功。

Sensor 新场景保持实际成本15SP、持续20秒、exact selected ability 恢复冻结。为短夹具显式准备15初始SP，不冒称原生初始0被改写。启动 tick2 后601仍可选且伤140，602半开结束恢复9、命令拒绝；603开始恢复1/30SP。INVISIBLE9 immunity 不销毁原 child，不删除 camouflage17。Sensor 的 INVINCIBLE5 对 physical、arts、true 三包实际拒绝，HP100保持且没有 accepted packet。地图改写、源卡片和整关预定义组合不在这项 peer 范围。

两组公开输入（通用 deadline、完整20秒 Sensor）均在 `verify.py` 中实际断言 ordered CP resume 与完整 commands replay 相等，再将输入、命令、CP、回放和最终快照写盘。随后 no-opt 跨版本身份比较过严而报错；这种后置诊断没有使之前战斗断言变成失败或假成功。该完整日志和旧 helper 字节保留。`seal_completed.py` 校验17 passed 原日志、锁这些源码与原始输入，再用已冻结输入重新编译并再次实际恢复两个 CP 到最终快照，完成最终封存。未重复长 Sensor commands replay；报告明确其直接执行依据来自之前 helper 中早于后置诊断的真实断言。

独立 no-opt 的 M48/M49 两进程执行同一输入和 seed，58个事件。完整 snapshot、World、resources、scheduler、RNG、所有事件值逐项比较，只有88个实际身份路径不同：snapshot/checkpoint 的 program/runtime 四个根字段，以及真实 calculation trace（包含其规范 nested stage trace）的 registry runtime 指纹。报告逐条保留双方值与具体路径。没有递归删任意同名字段，没有排除规则、输入、参数、数值或事件。本次不称 raw bytes 跨版本相等；作者原报告也区分 program/runtime 身份变化。

scope 为原始字段闭包、声明数学接口、实际公开执行与回放；native checker、动画事件、原生状态机方法正文仍待后续反馈。当前用户要求参考网站与固定数据优先，client_verified=False 单列，不阻止这些真实消费者交付。本报告不签整关或客户端准确性收据。
