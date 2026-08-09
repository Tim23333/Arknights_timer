"""应用版本的唯一配置入口。

发布新版本时只需要修改下面的 VERSION，然后重新运行 backend/build_exe.py。
"""

# 用户可修改：支持 3.2.4、v3.2.4、3.2.4-beta 等写法。
VERSION = "3.4.3"


def _display_label(version: str) -> str:
    value = str(version).strip()
    if not value:
        raise ValueError("VERSION 不能为空")
    return value if value.lower().startswith("v") else f"v{value}"


VERSION_LABEL = _display_label(VERSION)


def windows_version_tuple(version: str = VERSION) -> tuple[int, int, int, int]:
    """将显示版本转换为 Windows PE 需要的四段数字版本。"""
    core = str(version).strip().lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    if not parts or len(parts) > 4 or any(not part.isdigit() for part in parts):
        raise ValueError(
            f"VERSION={version!r} 无法转换为 Windows 版本；请以 3.2.4 等数字格式开头")
    numbers = [int(part) for part in parts]
    if any(number > 65535 for number in numbers):
        raise ValueError("Windows 版本的每一段必须位于 0..65535")
    return tuple((numbers + [0, 0, 0, 0])[:4])
