# 固定十二人标准数据规范化

`tools/normalize_campaign_operators.py` 独立读取同一公开数据 pin 的标准 character_table、skill_table，
规范固定队伍和必要依赖；不导入 V1 或 V2，不执行天赋、技能、召唤或普攻。
产物 `packages/campaign/operators.normalized.json` 是有来源的输入与显式模型数值，
仍为 `source_normalized_model_profile_unvalidated`、runnable=false、model/client_validated=false。

```powershell
..\.venv\Scripts\python.exe tools/normalize_campaign_operators.py --fetch
..\.venv\Scripts\python.exe tools/normalize_campaign_operators.py
..\.venv\Scripts\python.exe tools/normalize_campaign_operators.py --check
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_operator_stats.py -q
```

## 来源与缓存身份

来源为 ArknightsAssets/ArknightsGamedata，固定 commit
`56aee3d6c5a29c3a0d192456d70d14252cbb0804` 的
`cn/gamedata/excel/character_table.json` 与 `skill_table.json`。
用 curl.exe 下载，TLS 校验保持开启，只允许 HTTPS 与 HTTPS 重定向；
成功 HTTP 请求及标准 JSON 表校验后才替换缓存。
完整源表留在 `../unpack_work/campaign_tables/`，提交子集而非无关全表内容。
`packages/campaign/operator_sources.lock.json` 保存 URL、commit、完整源字节 SHA256、
size、路径和 cache identity；不调用 GitHub API，不存账户资料。

已有锁的缓存不匹配会明确失败，只有显式 `--fetch --refresh` 可重新获取。
`--check` 不联网、不修复缓存，重新验证全部来源并构建完整结果，比较源、配置、
规范化工具 SHA、模型 profile、子集与所有状态，任何漂移都拒绝。
roster.reference.json 的完整 SHA 与其 frozen_sha256 一并绑定。
输出保留十二人的完整标准 character 行、所选技能全部等级，和四个必要依赖角色原始行及非空技能引用。

## 养成与属性边界

固定输入为 E2、level70、potential1/rank0、trust100、rank7/mastery3、native skill levels[9]、无模组。
阶段、等级上限、技能 ID、技能解锁、六次基础等级解锁及三次专精解锁均由标准表核查。
没有按角色名称拼 ID，character_skill_index 是角色技能列表零基位置，native_level_index=9 是所选技能表专三行，
两者不同。

本地旧表 favorKeyFrames=None 不能解释为零信赖。标准表确实存在 favor level0→50 的属性关键帧；
桃金娘 level50 为 DEF+50，凯尔希为 HP+400、DEF+40，陈为 ATK+50、DEF+50。
工具缺失 favorKeyFrames 时直接失败，绝不默认零。

`rounding_profile.id=campaign.linear_frames.favor_endpoint100.half_up.v1` 明确以下模型假设：

- 基础属性按真实关键帧做分段线性插值，使用十进制 JSON 数字构造精确 Fraction。
- UI trust_percent/2 映射到原生 favor level，封顶50；trust100 对应最高原生关键帧。
- 先相加未取整的基础与信赖，再将整数属性按 nearest/half away from zero 取整。
- 非整数属性保留精确有理数，并提供模型小数；不把原始浮点位模式整数当属性。
- 不把天赋、潜能、装备、技能 Buff 加进裸属性；它们须由后续通用规则分别执行。

**中间等级的客户端取整顺序和 UI 信赖映射仍待独立公式/客户端校准。**
原生关键帧端点与源表完全一致，但不能据此称所有 E2 70 数值已经官方精确。
client_formula_verified=false 保存在 profile 与每个 stats 对象中。
所有 base/favor/unrounded_total 都保存 numerator/denominator，增长 alpha 与信赖原生 level 也明确保存；
换取整规则无需重新猜成长来源。

例如桃金娘是实际 E2 maxLevel70 端点，基础 HP1565、ATK520、DEF300；本 profile 的 trust100 DEF+50 后模型 DEF350。
陈等中间等级则存在真实有理插值，最终整数是该模型 profile 的结果。
Python round(2.5)=2 与本 profile 取3 的反例已测试，不能悄悄换成另一种取整。

## 技能、天赋、trait 和召唤数据

每个 operator 保存 selected_skill.character_skill_index、skill_id、native_level_index、完整 character_skill_slot 与 level，
含标准 enum 形式的 skillType/durationType、duration、rangeId、prefabId、spData 与原始 blackboard。
SP 必需字段 spType/spCost/initSp/increment/maxChargeTime 缺失直接报错，不补零。

talents 按独立 talent slot 保存全部当前 phase/level/potential 可解锁候选及 selected_candidate，
完整 raw_character 仍保存未解锁/高潜候选；不会把所有历史升级候选叠加执行。
trait_raw、unlocked_trait_candidates、selected_trait_candidate 同样保留原始 BB 与 unlockCondition。
桃金娘潜一选25HP/s候选，潜能四档增强后的28HP/s不会进入当前候选；此反例已测试。

召唤依赖来自 roster.reference 的实际 token_ids 与 trait_character_ids，封存：
token_10002_kalts_mon3tr、token_10003_cgbird_bird、token_10009_weedy_cannon、char_4179_monstr。
标准 token 技能列表中多项 skillId 本来就是 null，输出保留 null_skill_id_slots，不猜成主人技能 ID。
其 owner成长、信赖继承和绑定仍为 pending，不在 token 上套十二人 trust100 公式。
`sktok_weedy_token` 由先前冻结的实际技能引用定位并在同标准 skill_table 中验证存在，
单独封在 linked_token_skills，runtime_token_binding_status=pending。
trait 引用的 char_4179_monstr 不能自动替代 Mon3tr token。

普通攻击保存 phase.rangeId 与 characterPrefabKey；range 坐标、普攻动作生效帧、弹道与伤害/治疗行为、
trait/天赋原生组件等不在这两个标准表中，逐角色列为 gaps。
有 prefab 字符串不表示 prefab 已解析或行为已实现；本产物没有让缺失普攻静默使用通用攻击。

## 测试与消费接口

23 项测试覆盖真实 E2 初始/最终关键帧、真实非零信赖、缺失 favor 拒绝、非法等级/潜能/信赖/模组配置、
技能索引与 SP 参数、缺失技能/专三行/SP、潜能增强反例、精确有理插值与取整反例、
token null ID 保留、全输出重新构建和坏缓存拒绝。

顶层 schema 为 `ark_sim.campaign_operators_normalized.v1`，包含 source_lock、roster_source、
normalizer_source_sha256、rounding_profile、subset_sha256、operators、dependent_characters、linked_token_skills。
后续技能 recipe 可引用 selected_skill.level；后续属性编译器应消费 stats.components/增长输入并显式选择同 profile，
不能忽略 client_formula_verified=false，也不能把裸属性直接当加入天赋后的最终战斗属性。
固定队伍的通关、技能原语与客户端帧对照仍按独立验收门分别推进。
