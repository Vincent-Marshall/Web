"""pytest 公共配置：把 backend/ 加入模块搜索路径，保证 app 包可导入。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
