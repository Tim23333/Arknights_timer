# M20 provisional independent review

本页不签 fixed-identity receipt、不 promotion、不代表完整阶段通过。所有复核只读 root 候选；primary 与候选代码未改。旧 bbd87 失败 JSON 和原 helper 保留，root 已另存其历史源码。

修订 core `db6134da42647f1691f8b6fb5318fa8bbbcc455b26b1dc59841d6c1eba95bdcc`，实际 import 来自 `D:/Arknights/Arknights_timer/unpack_work/campaign_m20_dormant_candidate/ark_sim`。九个独立 cases 2.94秒通过，报告 `validation/campaign/m20_dormant_peer_db6134.json` SHA `d76cc72c7678bd6b7576a221fbf614a18ece3486a84255c720689fbf8fbf040a`，helper `tools/experiments/m20_peer/revised_review.py` SHA `c33b3014ffbe16c1f6158faf97e19b3dac761a7a8ae5d0945d734d7eb10e9551`，source/runtime/package/helper 开始与完成一致。

九项包括原 explicit SP/state 与无关 inactive freeze 求值反例现被拒绝、registration key 与同名 alias 分离、lifetime 从激活起算、公开付费命令 duplicate activation 全 rollback、直接 Behavior.transition 拒绝与 plan 停移停攻、同tick先emit再activate后emit的资源冻结快照0+1、七类 inactive target effect 不写入/调度/消耗RNG、actual NPC source capacity。CP/replay 只在真实初态与 recorded commands 的场景认通过，直接 API rollback/plan 查询单列 API scope。

晚激活快照的独立预期是先于激活发出的 signal 不得在之后的 reactor 得到SP，激活后的 signal 可以 +1；最终SP1。它并非从 actual 倒推。真实 NPC case 使用 root当时的 source wrapper原 definitions，只隔离阶段初态、加入合成 slotcard 与公开 activation命令；注册不占slot，同ID激活后占source1，后续部署实际被capacity拒绝，CP/command replay相等。重新核对实际 JSON 的 source_start/source_end，两者都锁 `335ca3e10fec3e85396ec39d1e2fc82a598268d28c45a7cd2ec14343067ad7c6`，capacity fixture program是 `199bf95158e0dbc255101ec3e5a5334dab8be5a02ec442344900e69c2d616c86`；helper实际调用build并assert OUT==p。此前文档和回复写成0fd8是摘要身份错误，现纠正，旧report原字节不改。这意味着fixture definitions已包含SNIPER/SP等修订，但capacitycase没有断言Ptilopsis aura1.3，其数值见证仍仅Root另两例，不能扩大本case范围。

## db6134 仍有真实来源旁路

root要求进一步检查 Never-activated dormant作为低层公开 `Effects.execute` 来源。`tools/experiments/m20_peer/source_boundary.py` SHA `e182fe8d2a51019536b4c1f973c0934cd24ab2943a65629d6ce58261594d19a0` 实际运行，同core/helper开始与结束一致，保存到 `validation/campaign/m20_dormant_source_db6134_complete.json` SHA `04b8a1b78d7bbc7f60a967a93037725e3fd9353334da9ab1a88c9e860b65dd2a`。

| 独立来源边界 | 实际结果 | 预期 |
|---|---|---|
| state=dormant/activeFalse source2→active target3，SP delta3 | target SP10→13 | SP10，never-activated source不得执行战斗写入 |
| 同来源，ATK20 / DEF0 physical packet | target HP50→30，真实damage.accepted source2 | HP50，无accepted packet |
| 同来源，random imp概率1 | 一次sample、branch值0.1573060320214088，RNG改变 | 不消费RNG、不产战斗random分支 |

位置是 candidate `domains/effects.py` 的 `_execute` for-target入口：当前 guard检查 target.active，未区分 never-activated source。三个反例都是公开 Effect API；报告明确 API-only，不把直接调用当command replay。第一轮两个 damage case缺少独立夹具的def字段而报错，已保留 initial工具/JSON；补显式def0/mres0后才确认当前伤害数值，不把那个夹具错误列为core bug。

强正对照通过：先用公开命令激活 source2，t1用真实skill发射 speed10/距离2 packet，t2公开retire(reasondead)使source activeFalse/state dead，t7原packet仍结算20，target HP50→30，CP和recorded-command replay相等。原发射不是伪造 cast metadata。修订必须区分“从未激活 dormant”与“已激活后退场但仍保留已发 packet”，不能统一禁止所有 activeFalse source。root已收到反例，并决定保持正在执行的db6134 baseline身份，之后再修新候选。

实际NPC源 `Character` component6482971719307902808的 `_occupiedRemainingCharacterCnt`严格int1，已有真实 capacity consumer；native card/refund basis、UI、壁钟与native callback仍client_pending。上述微场景不会将1-11、固定12或36关总体验收升级。
