# M14：0-10原生波次结构的独立Timeline内容

本批保持0fb/legacy conversion draft/旧35胜利及CP/replay证明不变，创建新builder `tools/build_m14_mainline_00_10.py` 和新包 `packages/campaign/mainline_models/level_main_00-10.m14_timeline.json`。只用冻结M12 core bd60，未改任何核心或旧包。

## 独立发现与旧消费缺口

0fb使用flat waves，没有Timeline；原审计把managedByScheduler=true、dontBlockWave=false、maxTimeWaitingForNextWave=-1统一指向flat at_seconds并标consumed_math，不能证明这些门真正执行。它是实际source/math consumer gap，不能以client_pending措辞或旧胜利来签完整转换。

新包把原1 wave / 5 fragments / actions逐项重建。SPAWN保留native count、preDelay、interval、managed、blocks_wave=not dontBlockWave、blocks_fragment、wave pre/post delay和max_wait。数量35、五敌类、17实际used routes保守不变；重复采用一个源action/count而非flatten为不同原点。出生实例保存真正play/wave/fragment/action origins。负timeout选择明确 `managed_clear + wait_for_clear` 数学policy，native sentinel/body仍待对照。

原source所有随机/group/preview等字段保存在native_action metadata；没有清门旗迁就旧命令。新aliases明确绑定w/f/a/repeat，源敌定义、route geometry/flags、placement和source indices均保持。

## 即时UI profile

M12 effects不能有跨tick managed成员。原本关STORY/INFO均blockFragment=false，因此本批显式采用**zero-lifetime logical UI completion**：在其真实action tick发started，观察全部五条真实故事commands或INFO payload，实际ack_finished并释放input_lock。同tick完成无存续member，原managed/dontBlock/blockFragment和w/f/a索引完整保留，不是把旗标unsupported静默删掉。

story参考实际raw TextAsset文件SHA与脚本SHA核验，五条Header/Popup/Blocker文本与冻结旧UI commands逐项相等；文字仅opaque metadata。UI payload指向 `timeline.action.origins.action_start`；对应timeline.action实际记录captured origins。native wall-time/pause/ack算法仍client_pending，不能将这个profile迁移到需异步blocked的Chapter01 STORY_a。

UI零life等价独立测试：插入started/commands/ack-finished同tick，inputlock无残留；敌人出生时点及剩余pending与不插UI完全相同。SPAWN门并非这项优化，真正进入Timeline membership/gate。

## 定义和options保留

每个实体/能力/Buff/selector/rule等原sections按相同UTF8 JSON编码逐字节比较相等；map、resources、rules、parameters、objectives、seed、12 deck都不变。独立native options检查deploy_capacity、life、DP初始/容量/周期与率、move multiplier、steering以及全部非活动options。不改人物角度、坐标、技能、天赋或敌行为来获得新胜利。

新timeline/scenario身份和metadata改变，必须有新战斗验证。不能复用0fb全程CP/replay为此新包证明。

## 实际反例与短prefix

四个新独立tests **4 passed in 38.35s**，日志 `tools/experiments/m14/final.log`：

- native35/17routes/5敌、wave/fragment/action结构及所有SPAWN flags/时间逐项相等；所有canonical sections/地图/12deck/options保持。
- 合成两wave实际首enemy仍alive时，negative wait_for_clear确实停在wave_gate。记录withdraw60后，post30＋下一wave pre30，第二birth为120；captured origins精确为play0/wave90/fragment120/action120，CP及commands replay一致。
- blocks_fragment=true实际阻同wave下一fragment；零life UI不改变birth/gate/pending且无inputlock泄漏。
- 新内容实际300tick prefix，CP150恢复及完整记录命令replay一致。

最后prefix另保存 `validation/campaign/m14_00_10_prefix.json` / `prefix.log`：只选择旧固定命令at0部署Myrtle和270 S2，**2 accepted / 0 rejected、0kill / 0leak / 33 pending、21038 events**。不是整关执行，没把其余十条命令删改后称新固定全关脚本。

实际runtime来自 `D:/Arknights/Arknights_timer/unpack_work/campaign_m12_projection_candidate/ark_sim/__init__.py`，起止bd60。prefix program `cc8d8eb6a735add442c57c0247a251cca7543aaf02d798d6acd070bc63edecb2`，runtime `5663fcbb8a262cbec9d619b7e63b8223af04f569493e0bd74fa4c9c6065dcf90`。

## 冻结SHA与后续

- builder：`7e53a58f2b687e83af13a999b5246f887b7ae1498aef4ae71a126dfb2f4792d4`
- model：`83bfa1829958f80a4f1da95740466326db3f5a8c7143737d728887b3670116d2`
- independent tests：`cb3c72e8fa67d97dd9cd7769ab7779f6bed73c2761ab3c021e09787a6839fbad`
- prefix evidence：`edfd79f78e8e1d4638154ce83306dffd93ee719e65837ef322e4be19d5aac4f8`
- original0fb input：`0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4`

generate/--check及Compiler240defs实际通过。Root将记录新完整固定commands并执行新内容三路全程；不通过关闭managed门迁就旧脚本。未签receipt、未升formal36、未提交推送。
