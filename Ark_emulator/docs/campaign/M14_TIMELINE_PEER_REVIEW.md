# M14波次来源与实际门独立复核

本复核读取原native关卡与冻结M14包，未调用作者build/assert函数来推期望，未改作者、旧包或bd60核心；实际导入固定M12候选。没有formal receipt。M14输入SHA83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2。

新7个bounded检查全部fresh通过。Source projection对raw波次逐action核35人口/17route/5definition、所有delay/count/interval/pre-post/maxWait/fragment grouping、SPAWN managed/block flags、完整bottom-up route/placement，与M12全部canonical定义及地图/roster/resources/rules/parameters/objectives/seed一致。Story/Info只发source观察事件，不把它说成native callback；zero-lifetime profile保留flags，无影子actor。

实际managed门使用合成actor的公开manual true-damage skill在tick12杀死HP10敌人，不用withdraw或ctx改alive替代。wave gate及fragment gate都真正阻止后续出生；effect阶段死亡在下一phase0 tick13释放，post6tick＋次wave pre3＋fragment pre3＋action3使第二敌tick28出生。实际origins={play_start0,wave_start19,fragment_start25,action_start28}。

有限timeout独立case：首wave gate起0、timeout6、post9，使下一wave_start15；old member在tick20被真正skill杀死，不得重置已有新wave/pre-delay wake；后pre9/fragment12/action3使第二敌tick39出生，origins={play_start0,wave_start15,fragment_start36,action_start39}。该晚释放场景含完整CP和recorded-command replay。

UI场景直接消费M14实际story effects，tick6的started/ack_finished同tick、lock清理；只保留battle、一个killer、两个实际enemy，无额外UI/shadow actors。实际门与无UI场景相同：第一敌kill12、第二birth28、相同origins。native UI壁钟/确认callback及negative sentinel/body语义仍client_pending。

zero count放在真实Timeline且引用M14已注册随机placement rule：没有birth、没有spawn RNG、没有第一动作的pending人口；后续wave仍按真实计数运行。source负例六项独立拒绝：blocks_wave丢失、未知native flag、maxWait替换、delay替换、route坐标替换、WALK误换FLY；这是来源消费者审计，未把它伪称作者/core的拒绝逻辑。

四个实际状态成功场景（真实kill wave/fragment、UI、finite timeout）以及zero-count都断言完整snapshot CP续跑和记录commands回放相同。Source/负例是数据检查，分开说明，不凭合计pass覆盖未执行机制。根任务正在跑的M14整关长程只待其真实完成，不在本peer里提前算pass。

## 冻结独立文件

- `tools/experiments/m14_peer/verify.py`: `a321d283bcb5be202678dc9bd474fdfa20353ac0d2a17996a6b5ef33f820dd8f`
- `validation/campaign/m14_timeline_peer_frozen.json`: `b8ec831cc1ce363dd3a9f9ad167d0c4dc4131a4e57b209355465d95c13aa126f`
