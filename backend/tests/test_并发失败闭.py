"""硬约束：改期望与补投送达并发须失败闭。

- 期望写入带 CAS 前置版：陈旧基准 → 409，版本不被覆盖；
- 下发带所见期望版：版已漂移 → 409 拒发，不产令；
- 同基并发抬版恰一个成功，其余 409（由场景端点用线程真实竞争）；
- 快照被篡改 / 快照核不符 → 补投 409，令留在途，绝不按不明载荷送达。
"""

from conftest import 写期望


def test_CAS_陈旧前置版_409且版本不变(client, 设备):
    键 = 设备
    写期望(client, 键, "v1")  # -> 1
    写期望(client, 键, "v2")  # -> 2
    r = client.post(
        "/影子台/期望",
        json={"设备键": 键, "期望载荷": {"mark": "stale"}, "前置期望版": 1},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "期望版本冲突"
    # 当前版仍是 2，未被陈旧写入覆盖
    影 = [x for x in client.get("/影子台").json() if x["设备键"] == 键][0]
    assert 影["期望版"] == 2
    assert '"mark": "v2"' in 影["期望载荷"] or '"mark":"v2"' in 影["期望载荷"]


def test_下发基准版漂移_409失败闭_不产令(client, 设备):
    键 = 设备
    写期望(client, 键, "v1")
    client.post("/设备册/断线", json={"设备键": 键})
    前 = len(client.get("/指令廊").json())
    # 调用方以为在 v9，实际 v1：拒绝钉一个自己没见过的版本
    r = client.post(
        "/指令廊/下发",
        json={"设备键": 键, "动作": "x", "钉住期望版": 9},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "期望版本冲突"
    assert len(client.get("/指令廊").json()) == 前


def test_并发同基抬版_与_篡改闭闸_场景全绿(client):
    sc = client.post("/期望版本钉/场景/并发失败闭", json={}).json()
    assert sc["全部通过"], [a for a in sc["断言"] if not a["通过"]]
    assert sc["成功数"] == 1
    assert sc["冲突数"] >= 2
    assert sc["意外"] == []


def test_直接篡改快照_补投409_令留在途(client, 设备):
    from app.db import 连接

    键 = 设备
    v1, _ = 写期望(client, 键, "v1")
    client.post("/设备册/断线", json={"设备键": 键})
    号 = client.post("/指令廊/下发", json={"设备键": 键, "动作": "a"}).json()["令号"]

    c = 连接()
    c.execute("UPDATE 指令廊 SET 期望快照=? WHERE 令号=?", ('{"mark":"evil"}', 号))
    c.commit()
    c.close()

    r = client.post("/设备册/重连补投", json={"设备键": 键})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "钉版校验失败闭"
    row = next(x for x in client.get("/指令廊").json() if x["令号"] == 号)
    assert row["状态"] == "在途"  # 未送达


def test_核验口多别名都返回五字段(client, 设备):
    键 = 设备
    写期望(client, 键, "v1")
    号 = client.post("/指令廊/下发", json={"设备键": 键, "动作": "a"}).json()["令号"]
    别名 = [
        f"/期望版本钉/核验?令号={号}",
        f"/核验?令号={号}",
        f"/指令廊/核验?令号={号}",
        f"/期望版本钉/verify?cmd={号}",
        f"/期望版本钉/令号/{号}",
        f"/指令廊/{号}/核验",
    ]
    for path in 别名:
        r = client.get(path)
        assert r.status_code == 200, (path, r.status_code, r.text)
        j = r.json()
        assert j["令号"] == 号
        assert "valid" in j and "执行载荷" in j and "当前期望版" in j


def test_核验不存在令号_404(client):
    assert client.get("/期望版本钉/核验", params={"令号": "CMD-nope"}).status_code == 404
    assert client.get("/期望版本钉/核验").status_code == 400
