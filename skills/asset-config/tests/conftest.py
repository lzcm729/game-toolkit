"""把 asset-config 与 generate-assets 的 scripts 都加进 sys.path。

check 必须复用 generate-assets 的加载与渲染逻辑 —— 两边各写一套解析，
同一份 yaml 就会得出不同结论，那正是这个仓库反复强调的「双口径」。
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (_HERE.parent / "scripts",
           _HERE.parents[1] / "generate-assets" / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
