# Arknights Timeline 桌面程序打包指南

## 问题背景

之前的打包方式会导致用户在没有安装 Python 的电脑上无法使用"打开寻址工具"功能，因为程序会尝试调用系统 Python 解释器来运行 `ak_timer_ui.py` 脚本。

## 解决方案

现在打包脚本会将寻址工具内嵌到主程序中，只生成一个 exe 文件：
- `ArknightsTimeline_v<版本>.exe` - 主程序（包含内嵌的寻址工具）

用户只需分发一个 exe 文件即可，点击"打开寻址工具"按钮时，程序会自动从内嵌资源中提取并运行寻址工具。

## 环境准备

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 PyInstaller

```bash
pip install pyinstaller
```

### 3. 可选依赖（推荐）

```bash
pip install numpy
```

numpy 可以显著加速内存扫描过程。

## 打包步骤

### 版本号

发布前只需修改 `backend/app/version.py` 中这一行：

```python
VERSION = "3.4.3"
```

打包脚本会自动把版本写入默认 EXE 文件名、Windows 文件属性、主页面顶部标题和
测试版诊断日志顶部。当前默认输出为 `ArknightsTimeline_v3.4.3.exe` 与
`ArknightsTimeline_v3.4.3_Test.exe`；`--name` 仍可覆盖输出文件名。

### 方法一：使用打包脚本（推荐）

```bash
cd backend
python build_exe.py
```

打包完成后，输出文件在 `backend/dist/` 目录下。脚本会自动：
1. 先打包寻址工具为临时 exe
2. 将寻址工具内嵌到主程序中
3. 清理临时文件

### 方法二：使用 PyInstaller 直接打包

如果需要更精细的控制，可以手动分步打包：

#### 步骤 1：打包寻址工具

```bash
pyinstaller --noconfirm --clean \
  --name AKTimerTool \
  --onefile --windowed \
  --icon aaa.ico \
  --paths ../tools/timer \
  --add-data "aaa.ico;." \
  --hidden-import ak_memory_reader \
  --hidden-import pymem \
  --hidden-import numpy \
  ../tools/timer/ak_timer_ui.py
```

#### 步骤 2：打包主程序（内嵌寻址工具）

```bash
pyinstaller --noconfirm --clean \
  --name ArknightsTimeline \
  --onefile --windowed \
  --icon aaa.ico \
  --paths .. \
  --add-data "aaa.ico;." \
  --add-data "../tools;tools" \
  --add-data "data;backend/data" \
  --add-data "app/static;backend/app/static" \
  --add-data "dist/AKTimerTool.exe;tools" \
  --hidden-import tools.timer.ak_memory_reader \
  --hidden-import tools.deploy_tracker.ak_deploy_reader \
  --hidden-import pymem \
  --hidden-import PySide6 \
  run.py
```

## 打包参数说明

| 参数 | 说明 |
|------|------|
| `--onefile` | 打包为单个 exe 文件（推荐） |
| `--onedir` | 打包为目录模式（调试用） |
| `--windowed` | 不显示控制台窗口 |
| `--console` | 正式版显示控制台窗口（手工调试用；不改变测试版） |
| `--skip-timer` | 跳过打包寻址工具（仅 build_exe.py） |

### 测试版诊断日志

```bash
python build_exe.py --test
```

测试版也使用 `--windowed`，不会弹出黑色 CMD 窗口。程序启动后会自动显示独立的
“测试版诊断日志”窗口，持续记录扫描、ADB、内存通道、实体名称/ID/属性解析状态和
未捕获异常。复现问题后点击“一键打包日志”，即可在
`%LOCALAPPDATA%\ArknightsTimeline\logs` 生成可发送的 ZIP 诊断包。

## 输出文件

```
backend/dist/
├── ArknightsTimeline_v3.4.3.exe        # 正式版（版本随 VERSION 变化）
└── ArknightsTimeline_v3.4.3_Test.exe   # 测试版（独立诊断日志窗口）
```

## 测试打包结果

```bash
python test_packaged_exe.py
```

该脚本会：
1. 检查 exe 文件是否存在
2. 显示文件大小
3. 尝试启动程序测试

## 分发指南

### 给用户分发

1. 只需将 `backend/dist/ArknightsTimeline_v<版本>.exe` 分发给用户
2. 用户可以直接运行，无需其他文件

### 用户使用说明

1. 双击 `ArknightsTimeline_v<版本>.exe` 启动主程序
2. 点击"打开寻址工具"按钮启动内存扫描（定位游戏时间/帧数地址）
3. 首次点击时，程序会自动提取寻址工具到临时目录
4. **注意**：寻址工具需要管理员权限才能读取游戏内存
5. 敌人监控：MuMu 模拟器进关卡且场上有敌人后，点击"开始扫描"（约 1-3 分钟，
   仅首次/换关卡需要），完成后自动准实时展示所有敌人信息

## 常见问题

### Q: 打开寻址工具时提示"未找到内嵌的寻址工具"

**原因**：打包过程中出现问题，寻址工具未正确内嵌

**解决**：重新运行 `python build_exe.py` 打包

### Q: 寻址工具无法启动，提示权限错误

**原因**：pymem 需要管理员权限才能读取其他进程的内存

**解决**：
1. 右键点击 `ArknightsTimeline_v<版本>.exe`，选择"以管理员身份运行"
2. 或在程序启动后，当系统提示权限时选择"是"

### Q: 杀毒软件拦截 exe 文件

**原因**：PyInstaller 打包的 exe 可能被误报为病毒

**解决**：
1. 添加到杀毒软件白名单
2. 或在 Windows 安全提示中选择"仍要运行"
3. 或使用 `--onedir` 模式打包（减少误报概率）

### Q: 程序启动后界面显示异常

**原因**：可能是显卡驱动或系统主题问题

**解决**：
1. 更新显卡驱动
2. 使用 `python build_exe.py --test`，在独立诊断日志窗口查看错误信息并打包 ZIP
3. 检查系统 DPI 设置

### Q: 点击"打开寻址工具"没有反应

**原因**：可能是临时目录权限问题或杀毒软件拦截

**解决**：
1. 检查 `%TEMP%\ArknightsTimeline` 目录是否存在
2. 尝试以管理员权限运行主程序
3. 检查杀毒软件是否拦截了临时文件创建

## 开发调试

### 使用 onedir 模式

```bash
python build_exe.py --onedir
```

打包后会在 `backend/dist/ArknightsTimeline/` 目录下生成所有文件，便于调试。

### 正式版显示控制台

```bash
python build_exe.py --console
```

该参数仅用于正式版的手工调试。排查用户电脑上的问题时优先分发测试版，测试版始终
保持无控制台窗口，并使用独立诊断日志窗口。

### 查看 PyInstaller 日志

打包过程中，PyInstaller 会生成详细日志在 `backend/build/` 目录下。

## 技术细节

### 内嵌原理

打包过程分两步：
1. 先将 `ak_timer_ui.py` 打包为独立的 `AKTimerTool.exe`
2. 再将 `AKTimerTool.exe` 作为数据文件打包到主程序中

运行时：
```python
if getattr(sys, "frozen", False):
    # 从内嵌资源中提取寻址工具
    embedded_exe = Path(sys._MEIPASS) / "tools" / "AKTimerTool.exe"

    # 提取到用户临时目录
    temp_dir = Path(tempfile.gettempdir()) / "ArknightsTimeline"
    temp_exe = temp_dir / "AKTimerTool.exe"
    shutil.copy2(embedded_exe, temp_exe)

    # 运行提取后的 exe
    subprocess.Popen([str(temp_exe)])
```

### 模块依赖关系

```
ArknightsTimeline_v<版本>.exe (~85 MB)
├── PySide6 (GUI)
├── pymem (内存读取: 时间/帧数)
├── tools/timer/ak_memory_reader.py
├── tools/deploy_tracker/ak_deploy_reader.py
├── tools/enemy_health/ (敌人监控: adb + TCP 通道)
│   ├── bin/memsrv (设备侧内存服务, aarch64)
│   └── data/tables/enemy_handbook_table*.bin (敌人名称数据库)
└── tools/AKTimerTool.exe (内嵌)
    ├── tkinter (GUI)
    ├── pymem (内存读取)
    ├── numpy (可选，加速扫描)
    └── ak_memory_reader.py
```

### 临时文件管理

- 寻址工具提取到 `%TEMP%\ArknightsTimeline\AKTimerTool.exe`
- 每次启动时检查文件是否已存在且大小一致
- 如果一致则跳过提取，避免重复写入
- 临时文件会在系统清理临时目录时自动删除

## 版本历史

- **v1.0**：初始版本，单 exe 打包
- **v2.0**：分离主程序和寻址工具，解决 Python 依赖问题
