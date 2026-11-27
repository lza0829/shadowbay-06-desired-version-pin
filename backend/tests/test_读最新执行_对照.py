"""对照套 B：执行时读最新 —— 在途抬版后，补投当下拼当前期望，执行载荷漂到 v2。

与 test_钉旧版执行.py 形成两套自动化对照：同样“写 v1 → 离线下发 → 抬 v2 → 补投”，
唯一差异是取版策略，执行载荷分别落在 v1 与 v2，版源字段必须可区分。
"""

from conftest import 写期望, 核验


def test_场景端点_读最新对照全绿(client):
    sc = client.post("/期望版本钉/场景/读最新", json={}).json()
    assert sc["全部通过"], [a for a in sc["断言"] if not a["通过"]]

    v = sc["核验"]
    assert v["钉住的期望版"] is None
    assert v["执行载荷"]["mark"] == "v2"
    assert v["执行期望版"] == 2
    assert v["版源"] == "执行时读最新"
    assert v["valid"] is True


def test_在途只存动作_补投读当前v2(client, 设备):
    键 = 设备
    v1, _ = 写期望(client, 键, "v1")

    client.post("/设备册/断线", json={"设备键": 键})
    d = client.post(
        "/指令廊/下发",
        json={"设备键": 键, "动作": "应用期望", "取版策略": "读最新"},
    ).json()
    号 = d["令号"]
    assert d["状态"] == "在途"
    assert d["钉住的期望版"] is None
    assert d["期望快照"] is None  # 廊行只存动作，不存快照

    # 在途核验：没有钉版凭证，valid=false（与钉版套的在途即可核形成对照）
    前 = 核验(client, 号)
    assert 前["valid"] is False
    assert 前["钉住的期望版"] is None

    v2, _ = 写期望(client, 键, "v2")
    补 = client.post("/设备册/重连补投", json={"设备键": 键}).json()
    执 = 补["执行"][0]
    assert 执["执行载荷"] == v2  # 漂到新版
    assert 执["执行期望版"] == 2
    assert 执["版源"] == "执行时读最新"

    后 = 核验(client, 号)
    assert 后["valid"] is True  # 送达后留下执行版+执行载荷，可回溯同票
    assert 后["执行载荷"] == v2
    assert 后["版源"] == "执行时读最新"


def test_同一场景两策略_执行载荷分属两版(client, 设备):
    """最直接的对照断言：相同在途抬版，钉版得 v1，读最新得 v2。"""
    键 = 设备
    v1, _ = 写期望(client, 键, "v1")

    client.post("/设备册/断线", json={"设备键": 键})
    钉号 = client.post(
        "/指令廊/下发", json={"设备键": 键, "动作": "钉", "取版策略": "钉版"}
    ).json()["令号"]
    新号 = client.post(
        "/指令廊/下发", json={"设备键": 键, "动作": "新", "取版策略": "读最新"}
    ).json()["令号"]

    v2, _ = 写期望(client, 键, "v2")
    client.post("/设备册/重连补投", json={"设备键": 键})

    钉核 = 核验(client, 钉号)
    新核 = 核验(client, 新号)
    assert 钉核["执行载荷"] == v1 and 钉核["执行期望版"] == 1
    assert 新核["执行载荷"] == v2 and 新核["执行期望版"] == 2
    assert 钉核["版源"] == "下发时钉版"
    assert 新核["版源"] == "执行时读最新"
    assert 钉核["valid"] is True and 新核["valid"] is True
