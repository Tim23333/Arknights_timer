# M21 current combination independent review

本页只认当前独立组合候选 `campaign_m21_integration_candidate`，core `c069e0206c076b429750b3fd97a507c54fb8e34fee51376c2f979f434151b95e`。未修改primary、candidate实现、作者测试或冻结包；没有promotion、整关或native收据。079和其旧结果不迁移为当前通过。

实际stage inputs读取bytes后核SHA再JSONdecode：

- `packages/campaign/chapter01_stage_models/m21/level_main_01-11.partial.json`：`2fd475a0491c86b0ab8d48ff1a17b983e5156d23bc5ea20a77782c8484e77e33`。
- `packages/campaign/chapter01_stage_models/m21/level_main_01-12.partial.json`：`9aa6f6b6aceb2eb1f2ced0013025765742f305d2b31dbf045e6c13201424154d`。

新工具 `tools/experiments/m21_peer/review.py` SHA `df263612ef4e84b3b16201d51415dbe619bbbdc2dd8baa935f63cbcf86e353bf`。fresh5cases全部通过，报告 `validation/campaign/m21_peer/report.json` SHA `6e753888e0dc0427867a16a1f9000365d26f2741c17cd2dd809013c1bfd2fc54`。实际runtime import路径/core、两个pkg、catalog/preset、helper及66个实际source文件开始/结束一致；另核两pkg列出的source_locks全部真实存在，没有漏锁文件。五份真实fixture输入写文件，读bytes/hash后decode执行，完整路径与SHA在report.fixture_inputs。

## 三个跨模块独立交互

这三项是克隆当前实际包中definitions/rules的隔离fixture，不声称完整阶段。仅声明合成actor、初态/资源与公开命令，未改canonical W攻击/技能定义。与下面保持原生timeline的完整prefix严格分开。

1. Registered focus同ID激活后作为C4 attachment，public withdraw50后activeFalse/aliveFalse。tick18真实发射，114显式center_position仍爆炸；dead focus保持HP5000，living neighbor HP4254（470×1.8−100=746），area.members仅neighbor。CP/recorded-command replay相等，直接证明c069修复了注册attachment退场后的区域结算，正常成员仍selectable。
2. Registered W在0由public command激活，真实normal launch9，10由独立Director public retire(dead)使activeFalse。21仅已发packet结算370（470−100）；第二未发signal取消，target HP4630。CP/replay相等，未用伪造cast标记绕source门。
3. 声明通用entry/exit profile，C4 launch18，focus由route在30隐藏并捕获World portal状态；50由public command改owned terrain层，revision1导致路径缓存失效，但portal capture保持。114仍按attachment位置伤visible neighbor746，hidden focus不伤，CP/replay相等。不从tile名字推断最近配对，不把teleport计入移动距离。

## 两个完整原输入短前缀

两个prefix保持原scenario原生waves/timeline/controls、固定roster、NPC/EMP、map/options/源routes；工具将scenario初态深拷贝前后比较，没有删原机制获得通过。每个先跑150ticks，再2ticks CPcontinuation和完整recorded-command replay，结果精确相等。这只是前缀，不是victory或完整chapter。

1-11：开场只有真正注册事件，NPC活但inactive、未执行created初始化；native preDelay2.99按30Hz ceil在90激活同ID，实际容量1。首W在90出生；actor.spatial.route与program中原source action转换route完全相等。150时story_b逻辑delay锁仍在，timeline有managed member与control member；上一fragment actions已执行完，remaining_actions0合法，next fragment的20s从上一末action90起算，wake690。

1-12：EMP实际开场created一次并owned terrain overlay，effective buildable0；150tick累计SP5、battle DP15（原initial10+periodic1/s五次）。首W在30出生，route完全同原action。没有残留input锁，managed member仍待释放；下一fragment4s从上一末action30起算，wake150。没有把stage_source中的DISAPPEAR/WAIT/APPEAR改成平路，也没有删除原UI/Story控制。

## 边界与保留失败

初peer失败是新夹具断言前提错误，原helper/initial JSON保留：area事件正确字段是members而不是targets；immutable事件数组要与同类型比较；normal目标必须有声明的ground tag；remaining_actions0不能误当无pending成员或阶段完成。这些修正只动自己的review工具，没有退回同步/可用性实现、改canonical definitions或从actual输出反推伤害公式。

本批没有实跑完整1-11/1-12。W原生FSM/移动攻击许可、nativebody、碰撞/抛物线/area形状/回调、training card/UI/退款基准仍需原source与client边界；namespace别名和sidecar metadata不能替代这些执行证据。固定12/36目标保持，下一步仅源审计enemy FSM并提出独立candidate接口，不在冻结c069中实现。
