# 第三章 DEF200 地板模型

Root在既有M48通用field框架上生成独立source-bound内容，无core变化。源计划d7f1中的tile_defup实际Unity BuffTile组件3052194825931517446已重读，属性类型2／formulaItem0／loadFromBlackboard1，与3-8实际黑板DEF200一致。目标side1/motion3/category3、clearWhenLeft1逐源消费；虚拟我方owner和独立child表示保明确声明策略。

新包`packages/campaign/chapter03_tiles/defup.reference_model.json` SHA`79a0fc54e7509e1db5faafe477a3bce5a1c2aa4ab9e2af75018b93633ce77a59`，build/--check通过。任意tile key可以profile引用同module，无官方tile ID分支。source flat DEF200并非百分比／法抗，未附加不相干治疗或对空倍率。

四实际测试通过1.76秒：category2合法我方占格，ATK1000对基础DEF100的目标入格伤700、离格伤900，HP3000→1400；公开命令、ordered磁盘CP和完整回放相同。敌方side1／category4／target-free三负例保持900不受field加防。报告`validation/campaign/chapter03_tiles/defup_tests.json`。

原Buff maxStack/源side/getter/坐标精度仍待用户反馈，独立peer待安排。该包只实现DEF200地图consumer，不构成3-8完整输入或整关收据；sensor、crate、INVISIBLE9及新敌人依赖分别实现。
