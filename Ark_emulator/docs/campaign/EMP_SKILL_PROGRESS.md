# 第1章EMP技能与通用退场/字段过滤进展

## 真实来源

依赖为1-12预放置 `trap_002_emp`，E0LV10/favor0/potentialRank0、alias null。原生8行地图的(2,5)按topdown转换为(5,5)，方向UP。
官方固定pin range表实读x-4为3×3九格，与历史离线JSON一致；旧JSON没有替代当前source下载。
原始character/skill/prefab子树保留在`emp.source.json`，外部2025 tokens与local2026源差异继续标client_pending。

原始字段与CPP枚举实读：HP100/ATK1000（源level1 ATK100、level30 ATK3000，LV10线性插值）、block0/categoryTRAP_OR_ITEM2/ally1；
技能level1 SP需求5/初始0/TIME1，额外DP10，predelay.75、cooldown1.5、arts scale1、stun7。
ActionToOwner事件3为ON_CAST_END，withdrawSource/switchToDeadState/force均true；passive异常5为INVINCIBLE。

## M15技能slice

新独立候选从冻结M13复制，只增加通用`retire` effect的schema/actor上下文与真实Lifecycle调用，没有官方ID分支。
它以明确reason退场，不伪改HP；reserved battle不能被退场；控制路径需明确actor目标或selector。
EMP订阅真正`ability.finished`后再执行retire(reason dead)，HP仍100、没有combat.kill；不将任意固定时刻HP改零伪称native撤离。

`emp.partial.json`使用.75秒包/1.5秒cast-end数学profile，callback精确时钟仍client_pending。
受伤目标在packet时重选，ground/活敌/九格范围，无目标cast允许根技能付款；三种伤害均被INVINCIBLE接收钩子拒绝。
源异常STUNNED0映射move/attack/abilities暂停，7秒半开恢复，block资格未被误清空。

实际14项EMP测试通过、8.62秒，64项相关能力/生命周期兼容通过、14.45秒（64包含14，不累加）。
独立peer7项及泛化retire3项另证：正常/空目标付款、临时移入/移出目标、SP/DP失败原子性、HP保持、同tickfinish先于退场，
owner/真实child/lifetime/cast递归清理、退场后失败整体回滚、无policy演员和重复幂等、控制actor与battle边界。

第一轮两个root断言错误保留：周期driver计tick0，五周期在29/59/89/119/149完成，命令150可使用；
stun控制按time≥expiry半开恢复，即使expiry task尚未处理也不继续控制。仅修改独立预期时刻，不改实现迁就夹具。

## 已修的实际类别缺口

原EMP selector只过滤enemy/ground/alive，漏 `_targetCategory=DEFAULT1`，独立反例实际将device2也击中800。
原177候选/98f包及失败证据冻结。新类别候选f98a与`emp.category.json`另存，不重标原失败。
新增可复用selector field predicate：明确runtime/definition scope、mapping/list path、互斥equals/bits_any、明确default；
不通过getattr读任意对象属性，bool不当整数位掩码。EMP显式读取definition.metadata.native_category，mask1/default1。
运行态entity没有复制definition metadata，不能在那里误取default1导致device仍入。

21个root字段边界通过；原反例新版本expected/actual都3、4，deviceHP3000保持。
独立复核还覆盖category3含DEFAULT位允许、2/4/0/bool/string/null排除、不同字段scope及非法path/mask/schema拒绝。
今后关卡实体导入必须绑定真实native类别，source default1是明确普通实体模型约定，不等于全部设备都DEFAULT。

## 下一必需模块

EMP仍为partial：TrapMode的live tile buildability、保留passability、height/advancedMask、层优先级与退场恢复尚未执行。
源字段全部保留并作为model_gap，不因技能伤害/14项成功而提升完整装置或1-12。
下一实现应是通用owned terrain-overlay模块，mutable状态在World、checkpoint/replay可恢复、无官方deviceID分支，
数值和层合并规则可替换。base地图不能被不可追踪地就地写坏。
