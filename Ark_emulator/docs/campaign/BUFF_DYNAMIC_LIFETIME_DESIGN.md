# 动态Buff持续时间底座

第八章灼烧父Buff原生`statusResistable=YES`，数据声明`ONE_MINUS_STATUS_RESISTANCE`属性26、范围0.001–1000；原Buff对象同时保存lifeTime、remainingTime、existingTime。当前内容只在施加时按目标有效属性缩放duration，不能证明获得／失去抵抗后已存在Buff的剩余时长正确。完整模拟需要对此另有实际来源规则和消费者。

拟实现显式可配置`buff.lifetime_rate`计算契约及Buff的`lifetime`字段，支持任意自定义时间流速。默认Buff继续使用原expires_at固定任务，不改变旧内容的时钟或事件。启用时保存原始duration、剩余逻辑量、上次采样tick和当前rate，按公开规则决定每个区间消耗多少剩余量。

建议配置包含rule、parameters、严格是否在失活时计时、刷新时的剩余量策略。规则接收真实owner/source只读快照、实际Buff实例、有效属性、当前逻辑时钟及elapsed。返回有限非负rate；1为正常时间流，2为双倍衰减。方舟抵抗通过可替换内容provider解释为1／clamp(one_minus_status_resistance)，内核不识别游戏attribute26或角色ID。

完整生命周期要求：

- 刷新／extend和remove前结算上一区间，只在合法owned实例／generation上推进；重复或伪造定时回调不能推进剩余量。
- 重新计算到期任务后保持half-open expiry，原有periodic触发相位不因抵抗变化重启。
- 实例失活、原source退场、目标死亡／复生及Aura／Toggle移除遵循显式策略；旧代不能续接新代duration。
- Rate provider异常或后续remove callback异常须回滚剩余量、任务、RNG与事件；私有重入guard必须finally清理。
- 检查点和从头回放保存实际累计值及任务；连续与分段推进不因观察次数改变衰减。

待来源复核决定的关键政策是属性变化边界：上一帧rate作用于上一时间区间，还是在帧边界先读取新rate作用于该区间。应明确保存选定参考profile和冲突，不能用单纯重写expires_at掩盖区间计时。测试至少包括中途抵抗开／关、跨期刷新、同帧原到期／属性变化、源退场、死亡复生、极值rate、非数字／bool拒绝、latefault与真实CP/head。

隔离候选已经实现`buff.lifetime_rate`与Buff的显式`lifetime={rule,parameters,count_when_inactive}`。当前源码身份为`35bae3f7661680cf019c1a8c6cf2d932718e771e702ab0c1dbb84673945794e4`，父9ad保持原样，主目录未修改。owned callback保存generation、taskseq、phase和due；每tick先按上一rate消耗上一时间区间，再读取当前有效属性给下一区间。当前expires_at只为不超过两tick的可见性投影，实际移除由真实owned clock或periodic同刻expiry判断完成。

15项实际作者检查通过，冻结 [author_freeze](../../validation/campaign/chapter08_buff_lifetime_v1/author_freeze.json)（ad0f7eed...）。覆盖原30.5s恒定rate到915、中途300抵抗到608、450去抵抗到765、400刷新到858、陈旧manual回调、rate bool/negative/infinity拒绝、provider/remove latefault、zero暂停和expiry与periodic同tick禁止尾包。原b131候选同刻多发一包的真实失败记录保留，新expired_now纯判断后原断言通过。

源 [dragon_fire.module.v5.dynamic.json](../../packages/campaign/chapter08_consumers/boss/dragon_fire.module.v5.dynamic.json)（15c538d7...）实际CP301→620/head全状态和事件一致：第300帧抵抗使父608结束，独立child每30tick伤害、最后600，20包与真实HP7740核同。首包56／ramp解释仍作为可替换规则；动态timer修复不自动证明这些尚缺原生body细节。

Talula [dynamic.v6](../../packages/campaign/chapter08_consumers/boss/talula.dynamic.v6.reference.json)（616c4fea...）已编译组合，完整内容源准入与独立候选反例尚待完成。自己的完整1219套件6672和0-1/custom基线4471已经启动，freshpeer继续，不提前推广。用户客户端反馈阶段与来源模型继续分别记录。


独立周期复核发现35bae在两tick投影下丢失后续periodic任务（e28aedb9...真counter），即使CP/head一致也不合源。新V2候选ac6cee4f...只让真实lifetime_clock实例跳过nextperiodic的固定expires_at排队限制，最终periodic仍用expired_now实际remaining禁止到期包。原peer9个有效断言作者复跑通过，保持期望2/4、暂停2/4/6/8、刷新2/5/7、extend2/5/7/9/11；NaN/Inf原夹具参数编译先拒不算runtime反例，独立新pureprovider用例另行检查。原35bae自己的full/base和所有失败记录保，不推广已知周期gap。


V3进一步补max短覆盖不能削短旧剩余量，随后独立发现真实HP0等待的区间活跃状态误用当前值导致expiry13而非14。最终V4为7e76e49e...，在clock里记录上一counting和rate，区间消耗后才更新新值；独立26项唯一检查全部实际通过a5436141...／冻结6abb86e1...，原真实期待不变。Full86052／baseline22549继续，同名原候选维持各自failed／passed scope。

无选项比较081b6d8e...逐值验证三场景World／events，只允许实际core/program/runtime fingerprint字段差异；新增契约导致嵌套trace runtime摘要也改变。旧工具只允许顶层摘要而失败保noopt_failed_scope_v1，未忽略任何数值／事件语义字段。源burnv8绑定当前core，独立原da6两source证明保实际da6身份而不按metadata旧ac6记账。
