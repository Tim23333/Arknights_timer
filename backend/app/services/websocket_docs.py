"""Shared protocol documentation for the desktop dialog and local Web UI."""
import json

from ..field_policy import FIELD_REGISTRY
from .websocket_api import TOPIC_DEFAULTS, TOPIC_LIMITS


def api_documentation(address="ws://127.0.0.1:8765"):
    """Generate the actual registered field paths and negotiated topic limits."""
    sections = [f"# Timeline WebSocket v2\n\n游戏接口 `{address}/v2/game`；运维接口 `{address}/v2/ops`。",
        "## 三个独立开关\n\n采集关：不解析、不派生、不合成该字段，跳过独占额外内存读取；共享块仍可能读取。"
        "展示关：仅从本地展示投影移除。发布关：仅从 WS 投影移除。采集关优先于展示与发布。"
        "依赖冲突会拒绝整笔更改，不会自动开启其他字段。内部帧守卫、身份和会话校验不能关闭。",
        "## 帧与读取状态\n\n`data.meta.sourceFrame` 是来源逻辑帧，`acceptedFrame` 是整轮守卫结束帧；"
        "`latestKnownFrame` 是完成时计时器缓存的最新已知帧，无法确定时为 null，绝不反向改写来源帧。"
        "`policyGeneration` 是接受该数据的策略代际。每个实体的 `fieldStates[字段ID]` 提供"
        "`sourceFrame/latestKnownFrame/acceptedFrame/generation/collectionState/reason`。"
        "状态为 current（本次读取）、static（已验证静态元数据）、historical（最后已知历史值）、"
        "not_collected（未采集）、unavailable（不可用）。static 的 sourceFrame 可为 null，"
        "不意味着实时属性已采样；historical 保留原来源帧，不改标为最新帧。"
        "读取失败或未采集时省略对应值，不把内部默认 0 冒充成功。合法 0、false 和空数组则保留。"
        "来源帧落后不统一禁止发布；动态整帧通过原有守卫，异步详情保留其自身来源。",
        "## 订阅\n\n```json\n" + json.dumps({"type": "subscribe", "requestId": "example",
            "topics": {"battle": {"rateHz": 20}, "enemy_detail": {"rateHz": 2, "scope": "selected", "ids": ["enemy-业务ID"]}}},
            ensure_ascii=False, indent=2) + "\n```\n\n"
        "`rateHz` 是每秒最多发布次数，越大越频繁，不意味着新增游戏帧或加快内存采样。"
        "服务器在 `subscription.updated.data.topics` 返回 requestedRateHz/effectiveRateHz。"
        "详情 scope=all 指当前已实例化、可读的全部对象，不是整关预定敌人；selected 按 items.id 筛选。"
        "异步详情采样最多5Hz；发布频率与采样频率不是同一概念。",
        "取消订阅：`{\"type\":\"unsubscribe\",\"topics\":[\"enemies\"]}`。"
        "获取已捕捉完整本局操作历史：`{\"type\":\"deploy.get_history\"}`；该历史仍受采集和发布开关控制。",
        "## 消息信封\n\n`type/schemaVersion/sessionId/sequence/emittedAt/data`；"
        "schemaVersion=2。游戏首次消息 game.ready，运维首次 ops.status，后续主题消息通常为 主题.updated。"
        "运维 heartbeat 不代表游戏字段可用。新字段需先注册公开路径与依赖，再通过"
        "`WebSocketApi.publish_fields(domain, values, ...)` 提交完整接受批次；不得传原始指针。"
        "实体域 enemy/character/enemy_detail/character_detail 必须传非空字符串 entity_id，"
        "字段位于 data.items[]，并分别服从采集、展示和发布策略。",
        "## 传输与背压\n\n首次订阅快照与确认、错误和完整操作历史回复使用有界可靠 FIFO；"
        "实时帧按主题只保留最新待发快照，不挤掉可靠回复。可靠待发超过 32 条时，"
        "仅该过载连接以 1013 关闭，请重新连接和订阅；断线期间不保证送达。"
        "序号在实际发送时递增，发送前仍检查会话与策略代际。",
        "## 主题频率"]
    for topic, default in TOPIC_DEFAULTS.items():
        lower, upper = TOPIC_LIMITS[topic]
        sections.append(f"- `{topic}`：默认 {default:g}Hz，允许 {lower:g}–{upper:g}Hz。")
    sections.append("## 字段清单\n\n下列路径相对于 data（敌我及详情相对于 data.items[]）。"
                    "columns.* 是同字段的本地格式化文本，同样受开关控制；属性数字键为游戏 AttributeType 槽。")
    for spec in FIELD_REGISTRY.values():
        if spec.domain == "internal":
            continue
        sections.append(f"- `{spec.id}`（{spec.label}）：" + "、".join(f"`{path}`" for path in spec.paths)
                        + ("；采集依赖：" + "、".join(spec.dependencies) if spec.dependencies else ""))
    sections.append("## 可用性与安全\n\n无场上对象与读取失败是不同状态；字段自检会分别报告。"
                    "服务关闭后断开连接并释放端口；本地 Web UI 仍可展示。"
                    "服务仅绑定本机；公开协议去掉指针字段与诊断文本中的地址。此服务不是互联网公开部署入口。")
    sections.append("## 当前来源限制\n\n详情中的 attackRange/effectFrames 尚无现成来源，字段状态为"
                    "unavailable，reason=unsupported_in_source；不会为了完整清单虚构值。"
                    "isPaused 来自本次敌我帧的 BattleController 暂停键集合；读取失败为 null，"
                    "并非 false。timeScale 在确认暂停时为 0，未确认暂停状态时为 null。"
                    "暂停/恢复边界的连续帧行为仍需实机事件验证。")
    sections.append("## 敌人编号与历史记录\n\n`enemy.code` 对应游戏内存图鉴的 `EnemyHandBookData.enemyIndex`；"
                    "由已加载的 `EnemyHandBookDB → EnemyHandBookDataGroup.enemyData` 取得，"
                    "不采用本地数据表补值。首次定位在扫描阶段，不在每帧扫描图鉴。"
                    "图鉴未加载或版本校验失败时编号不可用；此前未定位过图鉴，开启编号采集后需重新扫描。"
                    "已离场且从未被采样的计划敌人保留已知名称、enemyId、编号及 lifecycle；"
                    "没有采样过的 HP、位置等实时属性省略，其 fieldStates 标为 unavailable。"
                    "若有成功采样的历史值，保留 historical 状态与原来源帧。")
    sections.append("## 离场与操作帧\n\n敌人 `endReason` 为 death（观测到 DEAD）、reach_exit（观测到 REACH_EXIT）、"
                    "finish_N（其他 finish 标志）或 departed（离场原因未知）。不以缺失血量的默认 0 判断死亡。"
                    "独立的 `finishReason: integer|null` 保留从 `Entity.finishReason` 内存字段读取的原始枚举，"
                    "不从 endReason 反推。0=NONE（未结束）、1=REACH_EXIT（到达出口）、2=HP_ZERO（生命归零）、"
                    "3=FALLDOWN（坠落）、4=WITHDRAW（撤退/撤出）、5=DEADLIKE_WITHDRAW（死亡式撤出）、"
                    "6=SILENT_WITHDRAW（静默撤出）、7=OTHER（其他原因）、8=HP_ZERO_WITH_NO_SOURCE（无伤害来源的生命归零）、"
                    "9=REPLACED（被替换）、10=RESPAWN_SELF（自身重生）、11=MOVE_LIKE_RESPAWN_SELF（自身移动式重生）、"
                    "12=MOVE_LIKE_RESPAWN_EXTERNAL（外部移动式重生）。未来未知编号原样保留；枚举来自 Entity 而非 Ability。"
                    "活跃实体可能返回 0；未观测到离场内存块、晚接入或读取失败返回 null，不沿用上一存活帧的 0。"
                    "终止状态可能先于原始标志变化：endReason=death/reach_exit 时 finishReason 仍可能为 0，"
                    "这两个字段独立保留；前端原因栏保留已确认分类，原始编号列仍显示 0。"
                    "离场后该字段为 historical，来源帧是离场观测帧，与血量/位置的最后存活来源帧分开。"
                    "`enemy.finish_reason` 独立控制采集、前端展示和 WS 发布；关闭采集或对应输出时省略该键。"
                    "关闭采集会清除原始原因缓存，再开启不会恢复已离场对象的旧编号；endReason 分类保持原有语义。"
                    "`endFrame` 是首次观测到离场时的逻辑帧，不保证等于游戏实际死亡帧；未知或关闭采集时不补值。"
                    "`enemy.end_reason/end_frame` 分别控制这两个字段。\n\n"
                    "同局重启后，若程序相对缓存通过进程/战斗对象/场上实例连续性及帧号校验，"
                    "计划敌人的已观测离场基础历史也会经同一接口发布。仍标 historical 并保留原来源帧，"
                    "不把旧 HP、位置或 finishReason 标成重启后的当前帧。换局底层归零事件会失效缓存，"
                    "与自动扫描开关无关；未知身份、帧号回退或无稳定计划身份时不强行恢复。\n\n"
                    "操作 events[].frame 来自计时器的时间—帧样本匹配；null 表示没有匹配样本。"
                    "timerCacheExact 为精确匹配，timerCacheInterpolated 为相邻实测样本插值；"
                    "不能把当前帧或 timestamp×固定帧率当成早期操作的真实帧。")
    return "\n\n".join(sections)
