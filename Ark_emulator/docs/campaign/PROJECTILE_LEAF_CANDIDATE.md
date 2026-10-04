# 弹道子记录性能候选

后续验证已全部闭合并推广：自己的1219项完整回归通过2328.94秒，收据
`b2c2941ad83a35eb1599e2962e0f20ee41699f2c33620d9b544cc68b79441655`；
基线收据`ea164ee6…`与独立四项／三组152981节点精确配对收据`cd0a1f57…`分列核验。
主目录精确两文件推广、101源码／catalog与固定候选相同，旧20e完整备份。
推广收据 `validation/campaign/chapter08_projectile_leaf_v1_primary/promotion.json`，
SHA `79aae79789891003ecad7faad0c61404d4530660a4144c9c692bd8db48b2734d`。
下文在途状态为当时历史，新的World内部fork仍另建隔离候选。

本候选基于已推广20e，源码身份为 `71d33fa18662ae4f19c326988448e4dbb2764e503eec7bf3058e63c6a1182be2`。
只修改 `kernel/world.py` 与 `domains/projectiles.py`，主目录和在途运行保持原字节。

旧弹道每次读取／更新一条记录时，会解冻并重新写入整张弹道表，成本随保留的历史弹道增长。
新候选增加World只读子树接口，锁内深度冻结所需记录；更新只提交当前记录路径。
轨迹、伤害、命中顺序、时钟、随机数和事件内容不变，不返回可变World引用；版本计数仍每次加一。

原有弹道／目标／回放和实际机关／退休后弹道断言50项通过，另3项只读、历史快照隔离、
路径默认值和版本／插入顺序检查通过。报告为 `selected_original_v1.json` 与 `views_author_v1.json`。

七行火雨实际推进至tick400，两版各保存约137MB完整检查点、事件和回放，2438条事件逐值相等。
只允许核心身份和两个实际runtime_fingerprint字段不同，没有忽略计算输入、上下文、资源或任务。
报告 `validation/campaign/chapter08_projectile_leaf_v1/source400_comparison.json`，
SHA `e1e74c5e9ddd605ef05dd80a8231a7836aa489a33ff4e0a2b17b19df3c219605`。

本次单对运行的模拟耗时为旧版68.57秒、新版43.96秒，约1.56倍；只是该输入的单次测量，
不作统计性能保证。候选自身完整回归、0-1基线和独立复核尚待完成，未推广。

精确两文件增量在 `tools/candidates/chapter08_projectile_leaf_v1`，manifest SHA为
`eea7dd056e8a31604fc2f0e2b7f19fa58a0c2e754fd9730dd538ef5dbb68da08`，已实际重建为同一源码身份。
