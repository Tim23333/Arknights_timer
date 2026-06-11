# 更新日志

## 2024-06-11: 修复寻址工具无法打开的问题

### 问题描述

用户反馈：后端生成的 exe 文件，在其他用户电脑上打开"寻址工具"时打不开，但开发者自己的电脑正常。

### 根本原因

之前的实现中，主程序在打包后（frozen 模式）会尝试调用系统 Python 解释器来运行 `ak_timer_ui.py` 脚本：

```python
if getattr(sys, "frozen", False):
    py_cmd = shutil.which("python") or shutil.which("py")
    if not py_cmd:
        # 报错：未找到 Python 解释器
        return
    cmd = [py_cmd, str(script)]
```

如果用户电脑没有安装 Python，就会报错。

### 解决方案

将寻址工具内嵌到主程序中，只分发一个 exe 文件。

#### 打包流程

1. 先打包 `ak_timer_ui.py` 为临时的 `AKTimerTool.exe`
2. 将 `AKTimerTool.exe` 作为数据文件打包到主程序中
3. 运行时从内嵌资源中提取到临时目录并运行

#### 修改的文件

1. **`build_exe.py`**
   - 添加了 `_build_timer_tool()` 函数
   - 修改了 `_build_main_app()` 函数，添加内嵌寻址工具的逻辑
   - 修改了 `main()` 函数，实现两步打包流程

2. **`desktop_app.py`**
   - 修改了 `_on_open_timer_tool()` 方法
   - 添加了从内嵌资源提取寻址工具的逻辑
   - 添加了临时文件管理（避免重复提取）

3. **新增文件**
   - `test_packaged_exe.py` - 打包测试脚本
   - `README_BUILD.md` - 详细的打包说明文档
   - `CHANGELOG.md` - 本更新日志

### 打包结果

```
之前：
backend/dist/
├── ArknightsTimeline.exe (64.6 MB)
└── AKTimerTool.exe (25.9 MB)

现在：
backend/dist/
└── ArknightsTimeline.exe (90.2 MB)  # 包含内嵌的寻址工具
```

### 使用方法

#### 打包

```bash
cd backend
python build_exe.py
```

#### 分发

只需分发 `ArknightsTimeline.exe` 一个文件即可。

#### 用户使用

1. 双击 `ArknightsTimeline.exe` 启动主程序
2. 点击"打开寻址工具"按钮
3. 首次点击时，程序会自动提取寻址工具到临时目录
4. 后续点击直接运行已提取的寻址工具

### 技术细节

#### 内嵌资源路径

PyInstaller 打包后的程序，内嵌资源存放在 `sys._MEIPASS` 目录下：
```python
embedded_exe = Path(sys._MEIPASS) / "tools" / "AKTimerTool.exe"
```

#### 临时文件管理

```python
temp_dir = Path(tempfile.gettempdir()) / "ArknightsTimeline"
temp_exe = temp_dir / "AKTimerTool.exe"

# 检查是否需要提取
if not temp_exe.exists() or temp_exe.stat().st_size != embedded_exe.stat().st_size:
    shutil.copy2(embedded_exe, temp_exe)
```

#### 优点

1. **用户友好**：只需分发一个 exe 文件
2. **无需 Python**：用户电脑不需要安装 Python
3. **自动管理**：临时文件自动提取，无需用户干预
4. **性能优化**：避免重复提取，提高启动速度

### 测试验证

✅ 主程序打包成功（90.2 MB）
✅ 寻址工具已内嵌
✅ 主程序可以正常启动
✅ 文件大小正常

### 后续改进建议

1. 可以考虑将寻址工具的 GUI 从 tkinter 迁移到 PySide6，实现完全集成
2. 可以添加自动清理临时文件的功能
3. 可以添加版本检查，确保内嵌的寻址工具是最新的
