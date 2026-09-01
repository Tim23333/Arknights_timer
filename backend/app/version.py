"""应用版本的唯一配置入口。

发布新版本时只需要修改下面的 VERSION，然后重新运行 backend/build_exe.py。
"""

import re

# 用户可修改：支持 3.2.4、v3.2.4、3.2.4-beta 等写法。
VERSION = "3.5.4"


def _display_label(version: str) -> str:
    value = str(version).strip()
    if not value:
        raise ValueError("VERSION 不能为空")
    return value if value.lower().startswith("v") else f"v{value}"


VERSION_LABEL = _display_label(VERSION)


def windows_version_tuple(version: str = VERSION) -> tuple[int, int, int, int]:
    """宽松生成 Windows PE 四段数字版本，永不限制显示版本写法。

    Windows 的 ``FixedFileInfo`` 只能保存四个 0..65535 的整数；应用自己的
    VERSION 则允许使用任意非空文本。这里提取文本中第一段点分数字，忽略前后缀，
    没有数字时回退为 0.0.0.0，超大数字自动截到 Windows 能接受的上限。
    """
    match = re.search(r"\d+(?:\.\d+){0,3}", str(version))
    if match is None:
        return (0, 0, 0, 0)
    numbers = [min(int(part), 65535) for part in match.group(0).split(".")]
    return tuple((numbers + [0, 0, 0, 0])[:4])
