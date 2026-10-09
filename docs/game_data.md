# 游戏版本数据

`game_data/` 是桌面端和内存工具当前使用的数据目录。替换它并重启程序即可
加载新数据；读取算法或协议发生变化时仍需要更新代码。

## 当前目录

- `manifest.json`：数据版本、Android 客户端版本、资源来源层和文件 SHA-256。
- `tables/`：基础包与热更按逻辑表名合并后的二进制表，文件名不含版本哈希。
- `catalogs/`：干员、技能、装备、敌人、关卡元数据、名称和动作生效帧 JSON。
- `offsets/android_arm64.json`：ADB 读取器使用的结构、枚举及部署/RNG 布局。
- `offsets/pc_x64.json`：PC 客户端的结构对照资料，Android 读取器拒绝加载它。
- `overrides/`：手工修正；更新脚本会保留这个目录。
- `reference/<平台>/dump.cs`：偏移生成来源。Android 文件只包含本工具依赖的
  字段/枚举，由模拟器运行中的 IL2CPP 字段偏移表提取，不推断受保护的方法表。

源码运行时默认读取仓库的 `game_data/`。打包后优先读取 EXE 旁的同名目录，
没有外置目录时读取内嵌数据。可用 `ARKNIGHTS_GAME_DATA_DIR` 指定其他完整目录。
选定的目录缺少必需文件时会报错，不会混入旧版本的数据。旧 `data/` 和
`tools/enemy_health/generated_offsets.json` 仅用于没有新版数据目录的兼容运行。

## 更新

1. 在官方启动器中完成 PC 客户端资源更新。
2. 启动并更新 MuMu 中的游戏，保持游戏进程运行，开启模拟器 Root。
3. 双击项目根目录的 `更新游戏数据.bat`。默认 PC 路径是
   `E:\Hypergryph Launcher\games\Arknights`，默认模拟器地址是
   `127.0.0.1:16384`。
4. 成功后重启桌面工具，检查诊断信息中的数据版本。

自定义路径和模拟器地址：

```powershell
.venv\Scripts\python.exe -m tools.game_update.update `
  --game "E:\Hypergryph Launcher\games\Arknights" `
  --android-serial 127.0.0.1:16384
```

更新流程先在 `.cache/game_update/` 中解包和校验，全部通过后切换正式目录。
失败保留原目录；上一次数据目录位于缓存的 `previous_game_data/`，便于回滚。
缓存包含 APK、CAB、中间 JSON 和日志，可以在更新任务停止后清理。解包工具
会在输入旁生成 CAB，因此脚本先复制输入到缓存，不向游戏安装目录写入。

ADB 始终明确指定本地模拟器地址，拒绝手机序列号，不使用默认连接设备。
更新过程中会读取 MuMu 的安装包和运行中进程的结构表，不修改游戏内存。
本机未下载的资源不会被补成当前版本内容。

## 手工修正

例如调整一个名称，创建 `overrides/char_names.json`：

```json
{
  "char_002_amiya": "阿米娅"
}
```

名称、敌人数据库和生效帧分别使用 `char_names.json`、`enemy_names.json`、
`effect_frames.json`。结构修正使用 `overrides/android_arm64.json`，按原文件
的 `classes` / `runtime` 层级填写；只能修正 Android 数据，不能改变 `platform`。
字典递归合并，列表和标量整体替换。重启程序后加载结构修正。

生成文件的完整性校验用于检查提取结果。手工修正放在 overrides 中，避免
直接改动生成文件后无法判断它是否完整。新增 JSON 字段需符合对应加载器的格式。

## 校验

```powershell
.venv\Scripts\python.exe -c "from pathlib import Path; from tools.game_data import validate_bundle; print(validate_bundle(Path('game_data')))"
```

输出 `[]` 表示 manifest 中列出的生成文件哈希全部匹配。结构提取校验、离线
测试和真实关卡监控是不同的验证结果；完成源数据提取并不代表所有关卡已验收。

metadata 布局参考：
[Il2CppDumper v6.7.46](https://github.com/Perfare/Il2CppDumper/tree/8a521b9c180cf13499253f0818cbc729dca767cb)。
