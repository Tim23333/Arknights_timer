# Ark_emulator 子系统对接规范（v1）

> 本文件是 /root 与 level_calib / level_docs_sim 两个子智能体的接口契约。
> 双方各自实现自己负责的模块，并在交付前用本文件核对签名。

## 1. 常量与帧

- 逻辑帧 30 tick/s（`consts.TIME_ROUGH_LOGIC_RATE`），`tick` 从 0 开始。
- 所有移动/冷却/持续效果以 tick 推进；1 秒 = 30 tick。
- 位置单位为格，`moveSpeed 1.0 = 1 格/秒`，每 tick 位移 = moveSpeed/30。

## 2. 数据源（只读）

| 数据 | 路径 | 用途 |
|---|---|---|
| sim bundle | `G:\Arknights\ark_parser\enemy\data\stage_sim_bundle.json` | `levels[levelId]` 含 options/routes/waveTimeline/enemyDbRefs/enemyRoster/randomSeed；`stages[stageId] -> levelId` |
| 原始关卡 | `G:\Arknights\ark_parser\enemy\data\levels\level_main_01-01.json` | mapData.tiles / routes[].checkpoints / waves 原始结构（校准） |
| 敌人库 | `G:\Arknights\ark_parser\enemy\data\enemy_database.json` | enemyId -> [{level, data{attributes, skills, spData, lifePointReduce, motion, enemyTags}}] |
| 技能目录 | `G:\Arknights\ark_parser\enemy\data\skill_behavior_catalog.json` | enemyId -> {prefabKey, blackboard, priority, cooldown, initCooldown, spCost, enemySkill, abilities, buffKeys} |

## 3. 模块归属

| 模块 | 归属 | 文件 |
|---|---|---|
| 常量/属性/事件/RNG/伤害 | 已完成（勿改） | consts.py attributes.py events.py rng.py damage.py |
| 地图/寻路/实体/波次/战斗主循环 | level_calib | map.py entities.py waves.py battle.py api.py |
| 敌方技能/索敌/buff/异常/元素损伤 | level_docs_sim | skills.py targeting.py buffs.py ai.py |
| 契约/文档/示例 | /root | mechanics_spec.md README.md examples/ |

## 4. 实体接口（level_calib 实现，level_docs_sim 依赖）

`entities.Unit` 必须提供：

```python
class Unit:
    attributes: Attributes              # attributes.Attributes
    hp: float
    max_hp: float
    sp: float
    row: int; col: int                  # 当前格
    pos_x: float; pos_y: float          # 格坐标浮点
    buffs: list[dict]                   # {key, remaining_ticks, layers, add, mul, final_add, final_mul, source, tick_applied}
    abnormal: dict                      # flag -> {"ticks": int, "layers": int}
    def is_dead(self) -> bool
    def to_dict(self) -> dict           # 快照：位置/血量/攻防/SP/异常/buff 全量

class Enemy(Unit):
    enemy_key: str
    level: int
    route_index: int
    state: int                          # consts.EnemyState
    blocked_by: Operator | None
    block_volume: int
    move_speed: float                   # 倍率（1.0 基准），buffs 可直接改写
    attack_timer: float                 # 距下次普攻剩余秒
    skill_controller: EnemySkillController | None   # level_docs_sim 挂载
    def update_movement(dt)             # 沿 checkpoints 推进；到终点调 battle.on_enemy_reach_exit
    def set_state(state, reason=None)

class Operator(Unit):
    char_id: str
    deploy_tick: int                    # 入场时刻（仇恨公式用）
    direction: int                      # 0上1右2下3左
    range_shape: list[tuple]            # 相对格子列表
    attack_timer: float
    sp_cur: float; sp_max: float; sp_init: float
```

## 5. BattleController 接口（level_calib 实现，level_docs_sim 依赖）

```python
class BattleController:
    tick: int
    events: EventBus
    rng: SystemRandomClone              # 已按 rng_engines 对齐
    def get_enemies() -> list[Enemy]
    def get_operators() -> list[Operator]
    def get_tokens() -> list[Unit]
    def get_tile(row, col) -> TileData | None
    def path_distance(row, col, motion_mode) -> float    # distToFinal，仇恨公式用
    def apply_damage(target, amount, dmg_type, source, atk_scale=1.0) -> DamageResult
    def apply_heal(target, amount, source) -> float
    def add_buff(unit, buff: dict) -> None               # buff 结构见 §4
    def spawn_enemy_directive(key, row, col, route_index=...) -> Enemy | None  # 召唤型技能占位
    def on_enemy_reach_exit(enemy) -> None               # 扣生命点
    def emit(tick, type_, data) -> Event
```

## 6. 技能接口（level_docs_sim 实现，level_calib 调用）

```python
class EnemySkillController:
    def update(enemy, battle, tick)     # 每帧驱动：CD 递减、进行中技能推进、决策
    def should_cast_normal_attack(enemy) -> bool   # 攻击 timer 到期时询问：true 表示技能接管本次攻击
```

`ai.EnemyAI` 组合 skills/targeting/buffs：

```python
def update_enemy_ai(enemy, battle, tick)
```

## 7. 快照（/root 会基于 battle.snapshot() 落 demo，level_calib 保证字段）

```json
{
  "tick": 0, "t": 0.0, "lifePoint": 10, "cost": 10.0, "maxCost": 99.0,
  "deployed": [{"instId":1,"charId":"char_002_amiya","row":3,"col":4,"direction":1,
                "hp":100.0,"maxHp":100.0,"sp":0.0,"skills":[],"buffs":[],"abnormal":{}}],
  "enemies": [{"instId":1,"key":"enemy_1000_gopro","row":0,"col":0,
               "pos":{"x":0.0,"y":0.0},"hp":820.0,"maxHp":820.0,"atk":190.0,"def":0.0,
               "mres":20.0,"sp":0.0,"state":1,"routeIndex":1,"blockedBy":null,
               "buffs":[],"abnormal":{}}],
  "tokens": [],
  "map": {"width":9,"height":7,"occupied":{}},
  "events": [{"seq":1,"tick":0,"t":0.0,"type":"enemy_spawn","data":{}}]
}
```

## 8. 已知盲区（记录即可，不要阻塞）

- 物理 5% 保底是否作用于法术（暂按不作用）。
- 力量/重量对照表、costIncreaseTime 精确语义、弹道飞行时间。
- Boss 脚本型行为（Nodes.*）需要 xLua，本期用数据型敌人 AI 覆盖。
