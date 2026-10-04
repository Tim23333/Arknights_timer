# 首个主线目标依赖计划独立复核

2026-10-02，只读复核 `tools/build_mainline_dependencies.py` 与
`packages/campaign/mainline_dependencies/level_main_00-10.json`，新增独立
`tests_v2/test_mainline_dependencies_review.py`。没有修改生产源码或计划工具。

结论：首关计划状态为 **dependencies_resolved_not_executable**，runnable=false、model_validated=false。
当前没有完整十二人技能包或正式关卡运行结果；地图与路线转换说明仍是计划，不能把该产物交给
运行器当作已验收内容。独立八项加root四项依赖测试，**12/12通过，0.46秒**。

已实际核对：

- 敌库m_defined=false继承上级值；m_defined=true的0和false准确覆盖，未把它们当作缺省值。
  指定等级先按有效父层继承，最后应用overwrittenData；缺失请求等级明确拒绝，不使用相邻等级代替。
- 0-10普通目标保留35次出生，五个原生敌人：enemy_1000_gopro为14、enemy_1027_mob为5、
  enemy_1030_wteeth为2、enemy_1007_slime为12、enemy_1005_yokai为2。
  等级均为0，基础HP分别为820、1700、5000、550、800；飞行敌人ATK=0与motion=FLY均保留。
- difficulty=1。三条FOUR_STAR rune原文保留在native_runes/inactive_runes，applicable_runes为空。
  未把突袭1.2倍属性乘到普通关卡敌人。未来若有适用rune，工具会留下转换gap。
- 原生STORY与DISPLAY_ENEMY_INFO控制动作、完整波次脚本、options、predefines和使用路线均保留，
  没有为方便通关删控制或预定义。
- 地图9×13，共117格；二维matrix按palette索引映射，独立2×2交错例验证不是直接按palette顺序铺格。
  路线仍保留native bottom-up坐标，只说明未来row→rows-1-row转换，没有执行后宣称空间模型通过。
- 十二个所选技能ID与天赋原文完整保留，所有selected_skill机制仍列必需依赖；十一种尚未实现recipe、
  普攻/天赋不完整和敌方普攻prefab/生效帧等明确pending。唯一桃金娘S2仍是partial合成原型。
  计划没有十二个普通攻击占位能力冒充原生所选技能。

初次复核发现“任意--database文件仍声称同PIN”缺口；root新增enemy_sources.lock.json，
匹配固定commit及实际SHA。独立测试把源石虫HP改为999999，build明确拒绝输入身份失配。
当前DB SHA为`8630fe9c4fe23d3d22f09ed430da1dc308b15b5b5d98718f00181d08c5e186af`，
commit为`56aee3d6c5a29c3a0d192456d70d14252cbb0804`；计划同时锁定来源锁文件哈希。
计划文件与当前build产物精确一致。

在root确认核心暂冻结后，另重跑桃金娘技能10项、事件资源既有11项和独立13项，
**34/34通过，35.40秒**，其中包含技能checkpoint/input replay精确比较。
这些验证证明所列原型和事件资源模型门，不能提升该主线目标状态或客户端准确性。

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_mainline_dependencies_review.py tests_v2/test_mainline_dependencies.py -q
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_skills.py tests_v2/test_event_resources.py tests_v2/test_event_recovery_review.py -q
```
