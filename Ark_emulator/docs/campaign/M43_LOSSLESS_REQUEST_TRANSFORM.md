# M43 可组合伤害请求变换

独立复核发现原gazebo graph重建effect时无条件读取attack/defense/resistance，且只保留七字段。固定温蒂的真实距离规则不绑定ATK/DEF/RES，公开技能因此被拒绝；完整失败输入、命令、事件、源码身份存`validation/campaign/chapter02_fields_peer/weedy_distance_original_failure.json`。原25d8数值包与b35e field包保持冻结。

新候选`campaign_m43_request_transform_candidate`从M38 2165建立，core `f58f3594fe12dbf35f070effba48984871469f4799f19d7004b24c0ab5bd6c11`，只新增纯provider `model.damage.request_field_transform`及注册。它要求显式field/factor/default，对指定数值字段做乘法，完整复制其它request数据，拒绝bool、非数、非有限和溢出，不读写World。字段名与乘数均可作者配置，没有角色或地形ID分支。

新数值包`buffs.lossless_request.model.json` SHA `2dc2d9afe003d35d25f5e1d2897d34d5996d3c83291595c8cc97e76230fade46`，仅把gazebo缩放graph改成scale×1.7的纯变换，原typed FLY2条件不变。新field包`fields.lossless_request.model.json` SHA `48c31d15e06bacdfa3d3c157e9ed9b6e17bbb52659880593c22d9047e4f8dfec`保来源独立child及qualification定义，锁新provider能力。

25项实际检查通过6.89秒，包含request字段/嵌套数据保真及输入不可变、非法操作数/溢出、真实温蒂distance.5×1200/1=600链且保存CP/完整重放、原field9项及damage hooks/scenario effects。温蒂当前距离规则有意不读scale，因此600不随gazebo改变；native真伤是否使用该插入点仍记用户反馈，不能从内部实现推断已实机正确。报告`validation/campaign/m43_request_transform/candidate_final.json`和patch保存，不覆盖primary或正在执行的版本。

独立15项fresh复核通过3.15秒，core f58前后不变，两个公开fixture完整输入、命令、保存检查点续跑与回放全等。旧物理/法术/温蒂反例使用新包均通过，另外检查任意nested metadata/parameters/value/distance/locks/amount/order/signed-zero保真，以及custom pipeline amount25+vector[1]3=28的公开伤害链。最终peer `validation/campaign/chapter02_fields_peer/m43/final_review.json` SHA `ff7acdc2cde21266f2609b255d98359a4fe6f722702001365aa0197746abb9fc`；旧失败源及输入保留。组合M44仍有独立M42重入缺陷，不用本项通过覆盖该漏洞。
