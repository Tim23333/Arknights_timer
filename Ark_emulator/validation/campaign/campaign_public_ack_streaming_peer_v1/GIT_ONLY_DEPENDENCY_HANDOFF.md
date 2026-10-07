# Git-only 迁移依赖只读交接

本轮只读检查于用户暂停后进行，没有安装、构建、仿真、测试、数据打包或 Git 提交。最后由本 agent 推送并核对的 HEAD 为 `179caa16441fcf5abc248a8fb5583ad956b1477e`；Root 后续统一提交可能改变 HEAD。以下为已知关键路径，未遍历全部磁盘或全部历史候选。

## 物理位置与 Git 边界

Git root 是 `D:/Arknights/Arknights_timer`。很多依赖在此目录内但被忽略，普通 clone 无法带走；应与真正位于 Git root 外的依赖区分。

| 已知路径 | 用途与携带要求 |
| --- | --- |
| `Ark_emulator/ark_sim` | 已跟踪的默认08源码，当前 core08b6；不因搬迁宣称12e1/737已推广。 |
| `unpack_work/campaign_resource_channel_v1_candidate/ark_sim` | 默认08独立候选，freeze inventory99；可由固定 tracked 字节重建并逐inventory核，不能只留下绝对路径。 |
| `unpack_work/campaign_elemental_lease_v4_candidate/ark_sim` | 冻结94d2元素恢复版本及既有部分回放/反例身份。 |
| `unpack_work/campaign_owned_channel_phase_v2_candidate/ark_sim` | 冻结da218父版本；完整回归/基线/独立证据保持各自身份。 |
| `unpack_work/campaign_death_event_lookup_v1_candidate/ark_sim` | 冻结12e1 O1后继；仅一份death_spawns差量，已经完整回归/基线，未推广。 |
| `unpack_work/campaign_owned_interrupt_callbacks_v1_candidate/ark_sim` | 冻结737e拥有回调后继，完整回归已实际完成，9份源码差量已tracked；未推广。 |
| `unpack_work/campaign_owned_channel_phase_v1_candidate/ark_sim` | 旧阶段候选/反例身份，旧SourceDelta已tracked，不能重标为后继通过。 |
| `unpack_work/campaign_c10_chain_v1_candidate/ark_sim` | 冻结09c265链候选，旧独立链证明如需重放需对应全inventory；不可用当前08替代旧核心。 |

上述 unpack_work 被忽略。Git-only 迁移应保存完整冻结inventory对应的源字节，或有可追溯、逐字节重建工具；不是复制所有候选的缓存/日志。历史9a及7/10活跑82/94身份，需由 Root 的具体freeze、parent_source备份和交接记录选择，未在此重新枚举。只保存几个差量时，还必须保父链全部字节。

## 原生源关键路径

- `unpack_work/campaign_tables/enemy_database.json`、`character_table.json`、`skill_table.json`、`range_table.json`、`range_table.reference_56a.json`。`.download` 为另有临时文件，不作为已冻结来源。固定StageTable已tracked在 `Ark_emulator/packages/campaign/chapter10_source_prepare/stage_table.fixed56.source.json`；各章LevelData原文与源计划也已有tracked JSON。
- `data/battle/enm_pfb*.ab_unpacked/CAB-*`：敌方prefab和拥有节点；`data/refs/arts/enm_art*.ab_unpacked/CAB-*`：绑定Spine源。不能用新版同名文件替代冻结SHA。
- `data/battle/prefabs/*tiles.ab_unpacked/CAB-*`、`*tokens.ab_unpacked/CAB-*`、`*skills.ab_unpacked/CAB-*`、`*projectiles.ab_unpacked/CAB-*`：地图/预置物/技能/弹丸闭包。
- `data/anon/*_unpacked/CAB-*`：PPtr外部MonoScript闭包，NativeAssets按外部CAB名解析，需携带被源manifest实际引用的文件。
- `data/anon_textassets/buff_template_data.dat`：完整原BSON源，SHA `0c438b57b176e0fa430b5b982a58c7b524f4121aa8dbab33d3e647aa0fc1ee59`，约16MB。已提取模板JSON/base64是证据，部分工具仍核原文件SHA并重读它。
- `data/charpack/<actor_or_token>.ab_unpacked/CAB-*` 与 `data/chararts/<actor_or_token>.ab_unpacked/CAB-*`：固定12队员/召唽物原属性、模式、动画。源manifest引用的具体CAB应保持原字节；若序列化数据实际需要外部资源或同目录`.resS`，不能在未审引用的情况下全部丢弃。
- `unpack_work/release_20260831/hot_raw/*.dat`：故事/原TextAsset；第0章具体为 `main_00-10.dat`、`main_00-11.dat`。story JSON已带payload/base64/text与源SHA，但原文件仍是guard依赖。
- `unpack_work/campaign_external/battle_prefabs_tokens.20250327.ab`：第11章trap087精确探针，SHA `b9f16db4bfc8e8c880a0f90a1a7a74eda3b47c2188d0a151e5239d154716d475`，9,824,830字节。它是不同时间版本的补源探针，未合入原local闭包；搬迁不能消除 `source_only_with_gap`、branch DB level未定等既有边界。
- `Ark_data/dump.cs` 与 `Ark_data/Il2CppDumper_current/dump.cs`：原枚举/方法声明依据，通常已tracked。`script.json`、`il2cpp.h`、DummyDll/exe则被忽略；仅在后续确有native body/地址任务依赖时携带其准确版本，不混成源码已恢复。

Root应按既有source_locks、source/sha256对象和Unity external引用递归选择文件；本清单不是全素材目录可删的结论，也不证明迁移闭包已完整。必要的大于GitHub单文件限制的原文件可由Root打包成保持原SHA的可还原分块，不能更改原source身份。

## Python 与声明

本轮检查时 `D:/Arknights/Arknights_timer/pyproject.toml` 和 `Ark_emulator/pyproject.toml` 均不存在；git ls-files也未发现pyproject/uv.lock/poetry.lock/Pipfile。Root若随后新建迁移声明，应以后续冻结为准。

现有 `backend/requirements.txt` 声明 PySide6、pymem、psutil、`websockets>=16,<17`、UnityPy、numpy、pyinstaller、ziglang，多数无版本锁。它没有列 pytest 或 Spine-Asset。

`.venv/pyvenv.cfg` 指向真正位于Git root外的 `D:/python3.12.10/python.exe`，Python3.12.10；`.venv`本身被忽略，不是portable runtime。只读METADATA得到的当前直接版本：

| 分发包 | 本地版本 |
| --- | --- |
| UnityPy | 1.25.3 |
| Spine-Asset | 1.1.1 |
| pytest | 9.1.1 |
| psutil | 7.2.2 |
| numpy | 2.5.2 |
| PySide6 | 6.11.1 |
| Pymem | 1.14.0 |
| websockets | 17.0.1 |
| pyinstaller | 6.22.0 |
| ziglang | 0.16.0 |

这是已安装METADATA快照，不是完整传递lock或新环境通过证明。websockets17.0.1与现有 `<17` 声明不一致；暂停期间未调整。Spine解析使用 `spine_asset` v38 reader，工具还核installed_sources SHA；只锁包版本不足以证明旧reader字节身份。BSON目前有tracked自有解码器，未据此增加pymongo依赖。模拟核心主要为tracked标准库代码，source提取和完整测试另需要上述解析器/pytest；GUI与Windows内存工具的依赖应分别记录。

## 忽略与路径可移植性

根`.gitignore`明确忽略 `.venv/`、`venv/`、pycache/pytestcache、build/dist、frontend node_modules、`data/*`（仅README例外）、`/unpack_work/`、Ark_data巨大逆向文件、ark_parser派生data、私人缓存/env等。本轮 `git check-ignore -v` 已确认BSON、enemy DB、外部token AB和venv配置被忽略；dump没有对应忽略命中。不能仅靠已有clone声称原生源与候选全可重跑。

旧冻结JSON/工具包含 `D:/Arknights/Arknights_timer/...` 绝对source guard和candidate路径；移机后需要有审计的路径解析/物化策略，同时保旧artifact字节/SHA及内容身份。不能直接改旧报告绝对路径然后保原SHA或重标通过。多个launcher/lease仍固定 `E:/ArkSimLogs/runs`，这是真正Git root外的输出路径；Raw旧日志已清理的报告不是可续跑原日志。Git只需compact receipts/source证据；E盘输出位置与新机器租约/清理策略由Root迁移工具另定。

暂停后尚未做新环境安装、源闭包重构、运行验证或整关准入；这些不能在交接中标为完成。
