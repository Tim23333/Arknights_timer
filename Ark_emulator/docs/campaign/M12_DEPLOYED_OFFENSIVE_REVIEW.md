# M12 已部署六人端点与攻击扩展独立复核

本次只读复核冻结的7个端点和9个攻击扩展。没有修改核心、包、根工具或旧证据，没有签发正式验收收据。固定12人及36关目标保持不变。

两份记录均声明并实际保存 M12 bd60c068f0af7694e8e62c16868f4d310b6bb92681f8ebbf5d97814fba28ac11，输入包0fbba3f0548d2efaef97d7c1be98a620e65b6408755bfddbd49a132ef72fddf4。逐case的完整snapshot检查点续跑与初始场景＋记录commands回放比较在finish执行，并非仅将metadata标为通过。此复核核对代码、原始BB/帧字段与保存事件，不宣称重新运行全部16项。

|范围|独立数学核对|证据局限|
|---|---|---|
|风笛三击/溅射|650×2.2=1430；proc .25触发×1.3=1859；敌DEF50，主包1380/1809，溅射1809，排除主目标且不递归抽样；三个帧14/17/20|独立SHA派生Python MT模型，不是客户端RNG算法认证|
|风笛防御/阻挡/退款|366×2.2=805.2，1000物伤194.8；600tick半开恢复366、伤634；2→1真实WALK阻挡；DP raw13，两次退款13，70秒2100tick后2102再部署|第二次合法部署被覆盖，提前一tick拒绝没有在这9项中独立验证|
|能天使AUTO/五包|607×1.06×1.1−50=657.762；AS1.12仅缩放首windup .3→9tick；spacing .05量化2tick，非再次AS缩放；五包仅一次attack.accepted；首敌死后重新选其余四次|first packet实际HP1为clamped amount，不当作伤害公式1；攻击重选为声明模型|
|祝福|随机选一个活友军；自身及友军ATK+.06/maxHP+.1；1598当前HP与受伤友军保持绝对值；源退场清友军modifier；真实high tile＋deploy alias|本项没有实际受伤结算证明朋友ATK倍率；容量数学须结合已有容量独立证据；native currentHP策略仍pending|
|艾雅法拉|710×(1+.14+1.3)=1732.4；RES50为866.2；6目标由1+5，7个合格候选无放回随机选6，死亡/范围外不入，两个signal共12draw；55+(7+9u)部署SP；caster aura实际true114→100|当前随机、首signal与target count映射是明示模型profile；不能抹去native callback/client pending|
|桃金娘/白面鸮/塞雷娅端点|桃16×260及16DP；白面382三目标tick7/30重选；塞179.55双伤员与陈SP1|此7项不覆盖持续天赋、最高SP层、全部五层或所有源退出；新增support扩展另列|

身份记录须区分：six证据保存并结束核对operators、source lock、skill/talent等source_hashes。offensive文件的identity_at_start/completion仅直接锁自身工具、six工具、输入包；输入包锁住canonical定义，但不能把它描述成另外逐个原始source文件start/end校验。没有因此否定已实际执行的数学/回放结果。

没有发现本次声明范围内新的数值阻断。尚不能由7＋9点提升六人完整native闭包，路径变化本身不改变同字节bd60／同input0fb的program与runtime身份，此结果可作该实现／内容的机制证据；主路径实际导入及基线身份需另证，不能把candidate路径的命令称为主目录实跑；不同digest或内容不能迁移；正式关卡全程/其它角色闭包/执行门与客户端来源仍须各自证据。

## 冻结文件身份

- `tools/witness_deployed_six.py`: `8e18f48689a6b163a733f563c85cfeff44af9ab437a3c34145ee9363bb91ad5d`
- `tools/witness_deployed_offensive.py`: `712c80a95afc04d01620f4d7a5c5586ec01812fcdcda931b51d5cecb5167ce4e`
- `validation/campaign/deployed_six_m12_final_20261002.json`: `7bc690988034172badcc38ad4314e2efdae6c597786dc289604c3f21620475aa`
- `validation/campaign/deployed_offensive_m12_final_20261002.json`: `8a4bd4ce7e91689044e46526f7eacbbb0d5cf75ca6767b4940001f4c50373bf3`
