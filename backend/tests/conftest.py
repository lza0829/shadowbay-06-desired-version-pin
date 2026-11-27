"""期望版本钉自动化的测试夹具。

必须在 import app.* 之前把数据目录指到临时库，保证用例互不污染、也不碰仓库 data/。
"""

import os
import tempfile
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
_TMP = Path(tempfile.mkdtemp(prefix="sb-pin-pytest-"))
os.environ["数据目录"] = str(_TMP)
os.environ["预置目录"] = str(_ROOT / "fixtures")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import 连接  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import 初始化库  # noqa: E402

_清表 = ["补投条", "指令廊", "期望版本史", "影子台", "凭证轮", "设备册"]


@pytest.fixture(autouse=True)
def 每例清库():
    初始化库()
    c = 连接()
    c.execute("PRAGMA foreign_keys = OFF")
    for t in _清表:
        c.execute(f"DELETE FROM {t}")
    c.execute("PRAGMA foreign_keys = ON")
    c.commit()
    c.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def 设备(client):
    """注册一台设备，返回设备键。"""
    键 = "dev-test-pin"
    r = client.post("/设备册", json={"设备键": 键, "别名": "测试钉版机", "凭证指纹": "fp-init"})
    assert r.status_code == 200, r.text
    return 键


def 写期望(client, 键, mark, **额外):
    载荷 = {"mark": mark, "freq_hz": 10 if mark == "v1" else 20}
    body = {"设备键": 键, "期望载荷": 载荷}
    body.update(额外)
    r = client.post("/影子台/期望", json=body)
    assert r.status_code == 200, r.text
    return 载荷, r.json()


def 核验(client, 令号):
    r = client.get("/期望版本钉/核验", params={"令号": 令号})
    assert r.status_code == 200, r.text
    return r.json()
