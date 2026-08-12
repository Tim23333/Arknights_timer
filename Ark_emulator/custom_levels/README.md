# custom_levels — 自定义关卡样例

自定义关卡 JSON 结构（`build_level` 或手写）：

```json
{"rows": 6, "cols": 10, "tiles": [...], "routes": [...],
 "waveTimeline": [{"t": 0.5, "key": "enemy_1000_gopro",
                   "routeIndex": 0, "actionType": "SPAWN"}],
 "options": {"initialCost": 99, "maxCost": 99, "costIncreaseTime": 1.0}}
```

通过 `Simulator(custom_level=<json>)` 加载，配合
`Simulator(custom_enemies=[...])` 可完全自定关卡与敌人。样例：`smoke.json`、
`smoke2.json`、`rt_test.json`、`web_test.json`、`custom.json`。
