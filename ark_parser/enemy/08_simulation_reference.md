# 08 敌方行为模拟器落地规格

> 本文是“实现清单”：输入、每帧调度、状态机、技能、移动、异常、验证。
> 所有细节索引到 00-07 文档；结论分级【确认】/【推断】。

## 1. 输入数据

| 数据 | 文件 | 用途 |
|---|---|---|
| 敌人数值/技能 | `ark_parser/enemy/data/enemy_database.json` | (id,level) -> 属性/技能/SP |
| 敌人图鉴 | `data/enemy_handbook.json` | 文案/分类 |
| 关卡元数据 | `data/stage_enemy_usage.json` | stage -> levelId |
| 关卡内容 | 待解密 level_* 资产（见 02 文档 §1.1） | waves/routes/enemyDbRefs |
| 技能 prefab 参数 | `data/battle/enm_pfb_*.ab_unpacked`（UnityPy 可读） | 具体能力组件/触发参数 |
| 我方干员 | `ark_parser/character/data/characters.json` | 我方侧（可选） |

## 2. 全局参数（LevelData.Options，dump.cs:172015）

`maxLifePoint / initialCost / maxCost / costIncreaseTime / moveMultiplier /
maxPlayTime / characterLimit / enemyTauntLevelPow / deployCostPostDelta`。

## 3. 核心循环（30 tick/s，dump.cs:441464）

```python
dt = 1.0 / 30
while battle_running:
    scheduler.tick(dt)        # 波次/生成（02 文档）
    for enemy in enemies:
        enemy.state.tick(dt)  # 移动/攻击/技能/异常（00/04/05/06 文档）
        enemy.sp.tick(dt)     # SP 回复（03 文档 §4.3）
    resolve_projectiles(dt)
    resolve_blocks_and_path(dt)   # 05 文档 §4/§6
```

## 4. 状态机实现（状态转移表）

| 当前态 | 条件 | 下一态 |
|---|---|---|
| MOVE | 被阻挡且可战斗 | COMBAT |
| MOVE | 索敌命中且攻击就绪 | ATTACK |
| ATTACK | 被阻挡 | COMBAT |
| ATTACK | 无目标/打完 | MOVE |
| COMBAT | 阻挡解除 | MOVE/ATTACK |
| 任意 | 施加眩晕/冻结/浮空/麻痹 | STUN/FROZEN/LEVITATE/PALSY |
| STUN/FROZEN/LEVITATE/PALSY | 时长归零 | 恢复原态 |
| 任意 | HP<=0 | DEAD |
| MOVE | 到达终点 | REACH_EXIT（扣 lifePointReduce） |
| 任意 | 复活/闪现/消失 | REBORN/BLINK/DISAPPEAR |

## 5. 技能调度伪代码（完整）

```python
class EnemySkillRuntime:
    cooldown_timer; trigger_cnt; used_up; sp_cost
    def available(enemy):
        return (self.enabled and not self.used_up
                and self.cooldown_timer.ready
                and (self.sp_cost == 0 or enemy.sp >= self.sp_cost)
                and (self.ignore_silence or not enemy.silenced)
                and (not self.check_parent_active or enemy.mode_ok))
    def trigger_ready(enemy):
        return self.trigger.search(enemy)   # 目标在范围/条件满足

def on_action_frame(enemy):
    if enemy.state not in (ATTACK, COMBAT): return
    if enemy.has_casting_ability(): return
    wrapper = enemy.combatWrapper if enemy.blocked else enemy.attackWrapper
    for skill in sorted(enemy.skills, key=lambda s: s.priority, reverse=True):
        if skill.available(enemy) and skill.trigger_ready(enemy):
            return enemy.cast(skill, wrapper)   # 含 preDelay/生效/收尾
    if wrapper.main.ready:
        return enemy.cast(wrapper.main, wrapper)
```

## 6. 施放阶段机（Ability，03 文档 §5）

```
idle -> preDelay(起手,可打断) -> affecting(生效) -> finish
finish(reason): NORMAL/INTERRUPTED/OWNER_DEAD/TARGET_DEAD/PALSY
CD 重置：resetMainAbilityCdWhenCastEnd / waitFirstPeriod 语义
```

## 7. 移动积分（05 文档）

`位置 += moveSpeed * moveMultiplier * dt * 方向`，方向由路线检查点/寻路给出；
阻挡时速度归零进入 COMBAT；受控（UNMOVABLE/DURANCE/STUN…）期间不移动。

## 8. 异常计时（06 文档）

维护异常列表 {flag, duration, source}；每帧递减；到期移除并恢复旗标；
施加前查 AttributesData 免疫位；期间 SP 停/攻击停/技能停（视旗标）。

## 9. 验证方案（对拍真实战斗）

- 用 `tools/deploy_tracker`（BattleLogger 内存读取）导出真实操作序列，
  与模拟器生成的“敌人行动序列”对拍（时间/位置/技能）；
- 用 `tools/ak_live_rng`（战斗随机流）验证概率型技能（暴击/概率触发）的
  随机消耗与模拟器一致；
- 数值校准：baseAttackTime/attackSpeed 公式、preDelay/生效帧偏移
  （从 prefab 或实测补）。

## 10. 已知缺口

1. ~~level 资产解密~~ 已完成（2026-08-05）：Only Sign 剥 128B 头 + FB 解析，
   2854 关 -> `data/levels/*.json`、汇总 `data/stage_sim_bundle.json`
   （02 文档 §1.1 / 10 文档）；branches/optionalRunes 也已补齐（10 文档
   §7）；热更关卡检查过 PersistentData/Bundles/anon：593 个 level 资产与
   基线重合，无新增。
2. ~~敌方技能 prefab 逐技能参数~~ 已全量提取（2026-08-05）：
   `data/skill_behavior_catalog.json` 合并 blackboard×prefab（95.9%
   prefabKey 覆盖、1658 个技能实例），见 11 文档；剩 29 个 mode 变体/
   行为节点名未找到独立 prefab，部分 Trigger 无序列化参数。
3. 目标排序、priority 方向、眩晕期间 CD 是否暂停等为【推断】，建议实测校准；
4. 词条（Rune）改写技能参数的完整矩阵见 03 文档 §1.4。
