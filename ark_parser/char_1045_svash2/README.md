# 凛御银灰 (char_1045_svash2)

## 基本信息

| 字段 | 值 |
|---|---|
| ID | char_1045_svash2 |
| 英文名 | SilverAsh the Reignfrost |
| 子职业 | counsellor（策士） |
| 阵营 | kjerag |
| 编号 | KJ01 |
| 召唤物 | token_10057_svash2_eagle（风雪之眼） |

## 文件说明

| 文件 | 内容 |
|---|---|
| `char_1045_svash2_deep.json` | 完整嵌套数据（天赋/技能引用/潜能） |
| `svash2_final.json` | 基础字段数据 |
| `svash2_skills.json` | 技能数据（3个角色技能 + 3个鹰技能） |
| `svash2_strings.txt` | 所有中文文本（天赋/潜能描述） |
| `svash2_skills_strings.txt` | 技能详细文本 |

## 天赋

### 天赋 1: 雪境先驱
> 在场时，【谢拉格】干员免疫冻结，防御力+80（+20）且每秒回复2%（+0.5%）最大生命值；凛御银灰在场15秒后，防御力和生命回复效果翻倍

Blackboard: `hp_recovery_per_sec_by_max_hp_ratio`

### 天赋 2: 开放性开局
> 在场时向待部署区中加入"风雪之眼"，且会使待部署区按照部署费用排列。位于"风雪之眼"左侧的干员与自身初始技力+4，下次再部署时间-20%

Blackboard: `respawn_time`

## 技能

### 技能 1: 周旋的谋略
- 立刻获得部署费用
- 降低待部署区中最近干员的费用
- 部署后获得屏障

Blackboard: `cost`, `svash2_s_1[deck].cost`, `svash2_s_1[deck].shield`

### 技能 2: 御敌的锋锐
- 对前方6名敌人造成攻击力倍率的物理伤害
- 使敌人寒冷且隐匿失效
- 降低待部署区中最近干员的费用
- 使"风雪之眼"左侧干员部署时施放本技能范围效果（最多叠加2次）
- 可充能2次

Blackboard: `cost`, `atk_scale`, `cold`, `max_target`, `range_id`, `cost_scale_display`, `cnt`, `max_stack_cnt`

### 技能 3: 变革已至
- 攻击范围扩大
- 使敌人隐匿失效
- 攻击对直线范围造成物理伤害和脆弱
- 立即获得部署费用后持续获得24点
- 首次开启时交换待部署区中费用最高与最低干员的基础部署费用
- 技能期间"风雪之眼"变为可部署

Blackboard: `svash2_s_3[start_cost].cost`, `svash2_s_3[cost].cost`, `svash2_s_3[cost].interval`, `change_cnt`, `bird_atk_scale`, `damage_scale`, `cnt`, `weak[limit]`, `range_id`, `damage_scale_display`

## 潜能

- 部署费用-1
- 防御力+25
- 最大生命值+180
- 第二天赋效果增强
- 部署费用-1

## 标签

- 费用回复
- 支援
