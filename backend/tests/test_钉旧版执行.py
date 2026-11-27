"""对照套 A：下发时钉版 —— 在途抬期望版后，补投仍按钉住的 v1 快照执行。

覆盖硬约束：
- 令上必须留下可核期望版号 + 载荷快照（禁止只存动作名无快照）；
- 在线直达令同样钉版并留下版源字段；
- 在线直达 / 离线补投两条钉版路径都断言版源；
- 核验口给出 令号 / 钉住的期望版 / 当前期望版 / 执行载荷 / valid；
- 版漂是预期事实：钉版核验仍 valid，对影验不把版漂当钉版异常误报，
  也不拿钉住旧版与上报比对而误判“已齐”。
"""

from conftest import 写期望, 核验


def test_核验口契约与场景端点全绿(client):
    """规格主场景由场景端点固化；这里断言核验口五字段契约与版源。"""
    sc = client.post("/期望版本钉/场景/钉旧版", json={}).json()
    assert sc["全部通过"], [a for a in sc["断言"] if not a["通过"]]

    号 = sc["离线令号"]
    v = 核验(client, 号)
    # 规格要求核验口必须给出的五个字段（含英文 valid 键）
    for k in ["令号", "钉住的期望版", "当前期望版", "执行载荷", "valid"]:
        assert k in v, f"核验口缺字段 {k}"
    assert v["令号"] == 号
    assert v["钉住的期望版"] == 1
    assert v["当前期望版"] == 2
    assert v["执行载荷"] == {"mark": "v1", "freq_hz": 10, "firmware": "1.4.0"}
    assert v["执行载荷"] != {"mark": "v2", "freq_hz": 20, "firmware": "2.0.0"}
    assert v["执行期望版"] == 1
    assert v["版源"] == "下发时钉版"
    assert v["令源"] == "离线补投"
    assert v["版漂"] is True
    assert v["valid"] is True
    assert v["同票"] is True


def test_手工时序_写v1_离线下发_改v2_重连补投(client, 设备):
    """不借助场景端点，逐步打真实接口，断言执行载荷的版源。"""
    键 = 设备
    v1, _ = 写期望(client, 键, "v1")

    client.post("/设备册/断线", json={"设备键": 键})
    d = client.post(
        "/指令廊/下发",
        json={"设备键": 键, "动作": "应用期望", "取版策略": "钉版"},
    ).json()
    号 = d["令号"]
    assert d["状态"] == "在途"
    assert d["钉住期望版"] == 1
    assert d["版源"] == "下发时钉版"
    assert d["投递路径"] == "离线补投"
    assert d["期望快照"] == v1

    # 在途期间抬期望到 v2
    v2, _ = 写期望(client, 键, "v2")

    # 补投前：廊行已持久化钉版列与快照 JSON（硬约束）
    rows = client.get("/指令廊").json()
    row = next(r for r in rows if r["令号"] == 号)
    assert row["钉住期望版"] == 1
    assert row["期望快照"] not in ("", None)
    assert "v1" in row["期望快照"]
    assert row["快照核"].startswith("sha256:")

    补 = client.post("/设备册/重连补投", json={"设备键": 键}).json()
    assert 补["补投数"] == 1
    执 = 补["执行"][0]
    assert 执["令号"] == 号
    assert 执["执行期望版"] == 1
    assert 执["版源"] == "下发时钉版"
    assert 执["执行载荷"] == v1  # 不是 v2

    v = 核验(client, 号)
    assert v["valid"] is True
    assert v["执行载荷"] == v1
    assert v["当前期望版"] == 2


def test_在线直达令同样钉版并留版源(client, 设备):
    键 = 设备
    v1, _ = 写期望(client, 键, "v1")
    # 设备注册后默认离线；写上报会置在线，这里直接上报使在线
    r = client.post("/影子台/上报", json={"设备键": 键, "上报载荷": v1})
    assert r.status_code == 200

    d = client.post(
        "/指令廊/下发",
        json={"设备键": 键, "动作": "在线应用"},  # 默认策略也必须是钉版
    ).json()
    号 = d["令号"]
    assert d["状态"] == "送达"
    assert d["钉住期望版"] == 1
    assert d["版源"] == "下发时钉版"
    assert d["投递路径"] == "在线直达"
    assert d["执行载荷"] == v1
    assert d["执行期望版"] == 1

    v = 核验(client, 号)
    assert v["valid"] is True
    assert v["令源"] == "在线直达"
    assert v["版源"] == "下发时钉版"

    # 廊行里版源字段与钉版列都落库
    row = next(r for r in client.get("/指令廊").json() if r["令号"] == 号)
    assert row["版源"] == "下发时钉版"
    assert row["令源"] == "在线直达"
    assert row["钉住期望版"] == 1
    assert row["执行载荷"] not in ("", None)


def test_两条钉版路径_版源都可按令号回翻(client, 设备):
    键 = 设备
    v1, _ = 写期望(client, 键, "v1")

    # 离线补投路径
    client.post("/设备册/断线", json={"设备键": 键})
    a = client.post("/指令廊/下发", json={"设备键": 键, "动作": "离"}).json()["令号"]
    # 在线直达路径：重连后在线
    client.post("/设备册/重连补投", json={"设备键": 键})
    b = client.post("/指令廊/下发", json={"设备键": 键, "动作": "直"}).json()["令号"]

    for 号, 源 in [(a, "离线补投"), (b, "在线直达")]:
        v = 核验(client, 号)
        assert v["valid"] is True
        assert v["版源"] == "下发时钉版"
        assert v["令源"] == 源
        # 影子台/令册同源可回翻
        led = [r for r in client.get("/期望版本钉/令册").json() if r["令号"] == 号]
        assert led and led[0]["令源"] == 源 and led[0]["当前期望版"] == 1


def test_对影验_版漂不误判已齐_也不误报钉版异常(client, 设备):
    键 = 设备
    v1, _ = 写期望(client, 键, "v1")
    client.post("/设备册/断线", json={"设备键": 键})
    号 = client.post("/指令廊/下发", json={"设备键": 键, "动作": "应用期望"}).json()["令号"]
    v2, _ = 写期望(client, 键, "v2")
    client.post("/设备册/重连补投", json={"设备键": 键})

    # 端侧如实回声“它按钉版执行的 v1”
    client.post("/影子台/上报", json={"设备键": 键, "上报载荷": v1})
    验 = [x for x in client.get("/对影验").json() if x["设备键"] == 键][0]
    # 当前期望是 v2，上报是 v1：不得拿钉住旧版比对而误判已齐
    assert 验["对齐态"] == "未齐"
    assert 验["通过"] is False
    assert "影子未齐" in 验["说明"]
    # 但钉版本身无异常：版漂不等于钉版失败闭
    assert 验["钉版异常令数"] == 0
    assert 验["版漂令数"] >= 1

    # 端侧追平到当前 v2 后：无在途积压 → 通过；版漂计数仍在，但不导致失败
    client.post("/影子台/上报", json={"设备键": 键, "上报载荷": v2})
    验2 = [x for x in client.get("/对影验").json() if x["设备键"] == 键][0]
    assert 验2["对齐态"] == "已齐"
    assert 验2["通过"] is True
    assert 验2["钉版异常令数"] == 0
