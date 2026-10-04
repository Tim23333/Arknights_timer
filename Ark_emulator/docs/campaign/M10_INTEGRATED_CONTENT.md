# 下一冻结批次的综合内容

`tools/build_m10_integrated_content.py`组合最新targeting_v2、护盾/增伤修订与资源精确策略，
输出 squad.m10.json、level_main_00-10.m10.json、level_main_00-11.m10.json。
Primary f8不识别新增资源字段；该内容当前只在独立M10 candidate验证，不能误称生产已支持。

两处资源声明为陈SP.recovery_freeze_abilities=[selected S1]，凯尔希SP.recovery.interrupt_abilities=[host S3]。
在添加版本元数据与路线policy之前，删除恰这两字段的对象与原输入exact equal，避免误改其他技能/人才。
原生flag方法体与资源事件顺序继续client_pending。

新严格空间门实际揭露0-11的非零reachOffset还未执行：五个spawn实例上的MOVE点(4,6)均带x/y=.44。
新的综合wrapper逐实例保留原route/checkpoint/offset，为它们声明
rule/m9_checkpoint_cartesian和axis_signs(row=-1,col=+1)。因此实际目标为(3.56,6.44)，
而不是继续只按整数(4,6)移动。原客户连续几何/到达算法仍待对照，数学profile明确可替换。
旧M8探索胜利只代表旧输入，不能迁移到这份真实执行offset的内容。

编译实跑：0-10为240 definitions，0-11为245 definitions；M10实际catalog82（79+2路线+1资源冻结）。
敌方排序使用targeting_v2正确blocker方向；玩家规则没有全场替换。
整关/机制复核将以该批确切SHA、candidate implementation、命令和源身份分别记录。
当前仍没有签正式转换receipt。
