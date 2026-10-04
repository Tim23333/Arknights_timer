# M12 canonical 已部署支援扩展见证

此新工具只消费冻结 M12 candidate 与 `level_main_00-10.m12_projection.json`，不修改canonical攻击/技能/天赋定义。固定12人与36关目标不变；合成敌人、初始伤口/SP与显式probe能力是测试刺激，不冒充正式关卡。没有review receipt或full-native声明。

`tools/witness_deployed_support.py`复用冻结`tools/witness_deployed_six.py`的Compiler/Engine场景与finish。工具将源表、相关skill/talent包、输入包、双方helper及新test文件的起止SHA和两个独立进程测得的runtime digest封存。finish保存完整初态、记录commands、实际事件/RNG/actor只读摘要，同时断言checkpoint续跑与command replay的完整snapshot相同。没有ctx手写或属性calculator查询混入commands回放。

|case|独立预期与来源|
|---|---|
|Myrtle vanguard regen/source exit|talent源attribute13持续25HP/s；当前明示模型每tick25/30，30tick两先锋各+25，陈非先锋不回复；撤退源后停止|
|Ptilo TIME/event/highest/退出|选定TIME SP与天赋+.3；Suzu SUPPORT+.4取最高非叠成+.7；eventSP保持0；Ptilo撤退恢复普通TIME1而Suzu自+.4保留；固定deck Bagpipe给Myr初始6|
|Ptilo40秒模式|native preDelay .20000000298量化7tick；选技interval2.85−2.1=.75量化23，52包7..1180各382；1200半开移除，旧1203包抑制；normal恢复1234；SP1.3。固定state-clock模型，native动画signal/ramp不自证|
|Saria五层ATK/DEF|native BB interval20/max5/ATK.05/DEF.04；基础513/631，100秒641.25/757.2。canonical normal同格range0-1，实际物伤463→488.65→591.25；synthetic敌ATK2000在3000tick实际伤1242.8，当前HP1709.2|
|Saria arts与source exit|S3源倍率1.55，仅arts100→155；physical100−DEF50=50，true100；源退场arts100|
|Saria recipient emissionfreeze|真实179.55heal在tick16发出，recipient manual finish同tick稍后；发出时冻结使SP0，不能反应时解除后再+1|
|regen不返SP|Myr持续regen与Suzu115.2regen发regeneration.accepted而非healing.accepted；Saria不能因这两者返SP；Myr只deck6和tick29TIME1|

初轮预期错误保留：短项遗漏固定deck的Bagpipe初SP6、误将Myr原源持续恢复当1秒pulse；長项将Saria原点普攻的敌人放相邻格且无blocked关系，导致无攻击。均已另存失败记录，不当作核心缺陷，不改canonical定义迁就夹具。

最终全7 coherent实跑通过，pytest 7 passed in 211.64s (0:03:31)。每项checkpoint_equal/replay_equal均为True，source/core/package/helper起止一致。全部五层的首次界后伤害另由read-only `review_stack_endpoints.py`核629/1205/1817/2429/3005为488.65/514.3/539.95/565.6/591.25，另存数学审计JSON，没有额外模拟计数。最终结果与文件SHA以新`deployed_support_m12_extended.json`为准。旧短/长记录保持原身份。所有client方法体/时钟/RNG版本pending仍在输入源包内，此证据不删除它们。

## 最终冻结身份

- `tools/witness_deployed_support.py`: `86330e4a3026f309eca64a1faaa7d7eb03db5d1703d683176564f3b628f5d60f`
- `tools/experiments/deployed_support/tests/test_canonical_support.py`: `a5ec41e624d2f120c7884291c065151003b1d04f4944311cd0bfb3e8a2be5553`
- `tools/experiments/deployed_support/review_stack_endpoints.py`: `7a4efd06a558d22334a6b783922ecacc7dcad23f7d75a5e9f26dc7ec0b02963f`
- `validation/campaign/deployed_support_m12_extended.json`: `185448793dfb650dc846483062bad34887a85e6a6583b19013ec74165aa66ba4`
- `validation/campaign/deployed_support_m12_stack_endpoints.json`: `f262df97552d113892af6cb0ce5ba47b559d3704525ce8a3a3eeee60bb013fb0`
- `docs/campaign/M12_DEPLOYED_OFFENSIVE_REVIEW.md`: `7139fa62877b5ef1f2dd981d6b0b94354f06d4f7ac223c8f167e1aaa74817d44`
