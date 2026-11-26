import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import 连接, 预置目录
from app.seed import 现在

api = APIRouter()


def 行(r):
    return dict(r) if r is not None else None


def _读预置(名: str) -> dict:
    p = 预置目录 / f"{名}.json"
    if not p.exists():
        raise HTTPException(404, f"缺少预置 {名}")
    return json.loads(p.read_text(encoding="utf-8"))


@api.get("/健康")
def 健康():
    return {"ok": True, "服务": "影湾"}


@api.get("/总览")
def 总览():
    c = 连接()
    out = {
        "设备": c.execute("SELECT COUNT(*) n FROM 设备册").fetchone()["n"],
        "在线": c.execute("SELECT COUNT(*) n FROM 设备册 WHERE 在线='在线'").fetchone()["n"],
        "影子已齐": c.execute("SELECT COUNT(*) n FROM 影子台 WHERE 对齐态='已齐'").fetchone()["n"],
        "在途指令": c.execute("SELECT COUNT(*) n FROM 指令廊 WHERE 状态='在途'").fetchone()["n"],
        "积压补投": c.execute("SELECT COUNT(*) n FROM 补投条 WHERE 状态='积压'").fetchone()["n"],
        "凭证轮次": c.execute("SELECT COUNT(*) n FROM 凭证轮").fetchone()["n"],
        "空桩": c.execute("SELECT COUNT(*) n FROM 空桩").fetchone()["n"],
    }
    c.close()
    return out


@api.get("/空桩")
def 空桩列表():
    c = 连接()
    rows = [行(r) for r in c.execute("SELECT * FROM 空桩 ORDER BY 名").fetchall()]
    c.close()
    return rows


@api.get("/设备册")
def 列设备():
    c = 连接()
    rows = [行(r) for r in c.execute("SELECT * FROM 设备册 ORDER BY 更新时 DESC").fetchall()]
    c.close()
    return rows


class 设备入(BaseModel):
    设备键: str
    别名: str
    凭证指纹: str = "fp-init"


@api.post("/设备册")
def 写设备(body: 设备入):
    c = 连接()
    ts = 现在()
    旧 = c.execute("SELECT 1 FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone()
    if 旧:
        c.execute(
            "UPDATE 设备册 SET 别名=?, 凭证指纹=?, 更新时=? WHERE 设备键=?",
            (body.别名, body.凭证指纹, ts, body.设备键),
        )
    else:
        c.execute(
            "INSERT INTO 设备册(设备键,别名,在线,凭证指纹,入册时,更新时) VALUES(?,?,'离线',?,?,?)",
            (body.设备键, body.别名, body.凭证指纹, ts, ts),
        )
        c.execute(
            "INSERT INTO 影子台(设备键,期望载荷,上报载荷,对齐态,期望版,上报版,更新时) "
            "VALUES(?,'{}','{}','未齐',0,0,?)",
            (body.设备键, ts),
        )
    c.commit()
    c.close()
    return {"ok": True, "设备键": body.设备键}


@api.get("/影子台")
def 列影子():
    c = 连接()
    rows = [行(r) for r in c.execute(
        "SELECT s.*, d.别名, d.在线 FROM 影子台 s LEFT JOIN 设备册 d ON d.设备键=s.设备键 "
        "ORDER BY s.更新时 DESC"
    ).fetchall()]
    c.close()
    return rows


class 期望入(BaseModel):
    设备键: str
    期望载荷: dict = Field(default_factory=dict)


@api.post("/影子台/期望")
def 写期望(body: 期望入):
    c = 连接()
    if not c.execute("SELECT 1 FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone():
        c.close()
        raise HTTPException(400, "设备不在册")
    ts = 现在()
    影 = c.execute("SELECT * FROM 影子台 WHERE 设备键=?", (body.设备键,)).fetchone()
    期望文 = json.dumps(body.期望载荷, ensure_ascii=False, sort_keys=True)
    上报文 = 影["上报载荷"] if 影 else "{}"
    对齐 = "已齐" if 期望文 == 上报文 else "未齐"
    版 = (影["期望版"] + 1) if 影 else 1
    c.execute(
        "INSERT INTO 影子台(设备键,期望载荷,上报载荷,对齐态,期望版,上报版,更新时) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(设备键) DO UPDATE SET 期望载荷=excluded.期望载荷,对齐态=excluded.对齐态,"
        "期望版=excluded.期望版,更新时=excluded.更新时",
        (body.设备键, 期望文, 上报文, 对齐, 版, 影["上报版"] if 影 else 0, ts),
    )
    c.commit()
    c.close()
    return {"ok": True, "对齐态": 对齐, "期望版": 版}


class 上报入(BaseModel):
    设备键: str
    上报载荷: dict = Field(default_factory=dict)


@api.post("/影子台/上报")
def 写上报(body: 上报入):
    c = 连接()
    if not c.execute("SELECT 1 FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone():
        c.close()
        raise HTTPException(400, "设备不在册")
    ts = 现在()
    影 = c.execute("SELECT * FROM 影子台 WHERE 设备键=?", (body.设备键,)).fetchone()
    上报文 = json.dumps(body.上报载荷, ensure_ascii=False, sort_keys=True)
    期望文 = 影["期望载荷"] if 影 else "{}"
    对齐 = "已齐" if 期望文 == 上报文 else "未齐"
    版 = (影["上报版"] + 1) if 影 else 1
    c.execute(
        "INSERT INTO 影子台(设备键,期望载荷,上报载荷,对齐态,期望版,上报版,更新时) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(设备键) DO UPDATE SET 上报载荷=excluded.上报载荷,对齐态=excluded.对齐态,"
        "上报版=excluded.上报版,更新时=excluded.更新时",
        (body.设备键, 期望文, 上报文, 对齐, 影["期望版"] if 影 else 0, 版, ts),
    )
    c.execute("UPDATE 设备册 SET 在线='在线', 更新时=? WHERE 设备键=?", (ts, body.设备键))
    c.commit()
    c.close()
    return {"ok": True, "对齐态": 对齐, "上报版": 版}


@api.get("/指令廊")
def 列指令():
    c = 连接()
    rows = [行(r) for r in c.execute("SELECT * FROM 指令廊 ORDER BY 下发时 DESC LIMIT 100").fetchall()]
    c.close()
    return rows


class 指令入(BaseModel):
    设备键: str
    动作: str
    载荷: dict = Field(default_factory=dict)
    凭证指纹: str | None = None


@api.post("/指令廊/下发")
def 下发指令(body: 指令入):
    c = 连接()
    设备 = c.execute("SELECT * FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone()
    if not 设备:
        c.close()
        raise HTTPException(400, "设备不在册")
    指纹 = body.凭证指纹 or 设备["凭证指纹"]
    ts = 现在()
    令号 = "CMD-" + uuid.uuid4().hex[:10]
    if 指纹 != 设备["凭证指纹"]:
        c.execute(
            "INSERT INTO 指令廊(令号,设备键,动作,载荷,状态,凭证指纹,下发时,闭环时,说明) "
            "VALUES(?,?,?,?,'拒令',?,?,?,?)",
            (
                令号,
                body.设备键,
                body.动作,
                json.dumps(body.载荷, ensure_ascii=False),
                指纹,
                ts,
                ts,
                "凭证指纹与在册不符",
            ),
        )
        c.commit()
        c.close()
        return {"令号": 令号, "状态": "拒令", "说明": "凭证指纹与在册不符"}

    if 设备["在线"] == "离线":
        c.execute(
            "INSERT INTO 指令廊(令号,设备键,动作,载荷,状态,凭证指纹,下发时,说明) "
            "VALUES(?,?,?,?,'在途',?,?,'离线积压')",
            (令号, body.设备键, body.动作, json.dumps(body.载荷, ensure_ascii=False), 指纹, ts),
        )
        序 = c.execute(
            "SELECT COALESCE(MAX(序),0)+1 n FROM 补投条 WHERE 设备键=? AND 状态='积压'",
            (body.设备键,),
        ).fetchone()["n"]
        条号 = "Q-" + uuid.uuid4().hex[:10]
        c.execute(
            "INSERT INTO 补投条(条号,设备键,令号,序,状态,入条时) VALUES(?,?,?,?,'积压',?)",
            (条号, body.设备键, 令号, 序, ts),
        )
        c.commit()
        c.close()
        return {"令号": 令号, "状态": "在途", "说明": "离线积压", "条号": 条号}

    c.execute(
        "INSERT INTO 指令廊(令号,设备键,动作,载荷,状态,凭证指纹,下发时,闭环时,说明) "
        "VALUES(?,?,?,?,'送达',?,?,?,'在线直达')",
        (令号, body.设备键, body.动作, json.dumps(body.载荷, ensure_ascii=False), 指纹, ts, ts),
    )
    c.commit()
    c.close()
    return {"令号": 令号, "状态": "送达", "说明": "在线直达"}


@api.get("/补投条")
def 列补投():
    c = 连接()
    rows = [行(r) for r in c.execute("SELECT * FROM 补投条 ORDER BY 设备键, 序").fetchall()]
    c.close()
    return rows


class 断线入(BaseModel):
    设备键: str


@api.post("/设备册/断线")
def 断线(body: 断线入):
    c = 连接()
    if not c.execute("SELECT 1 FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone():
        c.close()
        raise HTTPException(400, "设备不在册")
    ts = 现在()
    c.execute("UPDATE 设备册 SET 在线='离线', 更新时=? WHERE 设备键=?", (ts, body.设备键))
    c.commit()
    c.close()
    return {"ok": True, "在线": "离线"}


@api.post("/设备册/重连补投")
def 重连补投(body: 断线入):
    c = 连接()
    设备 = c.execute("SELECT * FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone()
    if not 设备:
        c.close()
        raise HTTPException(400, "设备不在册")
    ts = 现在()
    c.execute("UPDATE 设备册 SET 在线='在线', 更新时=? WHERE 设备键=?", (ts, body.设备键))
    条们 = c.execute(
        "SELECT * FROM 补投条 WHERE 设备键=? AND 状态='积压' ORDER BY 序",
        (body.设备键,),
    ).fetchall()
    完成 = []
    for 条 in 条们:
        c.execute(
            "UPDATE 补投条 SET 状态='已补', 补投时=? WHERE 条号=?",
            (ts, 条["条号"]),
        )
        c.execute(
            "UPDATE 指令廊 SET 状态='送达', 闭环时=?, 说明='重连补投' WHERE 令号=? AND 状态='在途'",
            (ts, 条["令号"]),
        )
        完成.append(条["令号"])
    c.commit()
    c.close()
    return {"ok": True, "补投数": len(完成), "令号": 完成}


@api.get("/凭证轮")
def 列凭证():
    c = 连接()
    rows = [行(r) for r in c.execute("SELECT * FROM 凭证轮 ORDER BY 生效时 DESC").fetchall()]
    c.close()
    return rows


class 轮换入(BaseModel):
    设备键: str
    新指纹: str


@api.post("/凭证轮/轮换")
def 轮换凭证(body: 轮换入):
    c = 连接()
    设备 = c.execute("SELECT * FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone()
    if not 设备:
        c.close()
        raise HTTPException(400, "设备不在册")
    if body.新指纹 == 设备["凭证指纹"]:
        c.close()
        raise HTTPException(400, "新指纹须不同于当前")
    ts = 现在()
    轮号 = "ROT-" + uuid.uuid4().hex[:10]
    旧 = 设备["凭证指纹"]
    c.execute(
        "INSERT INTO 凭证轮(轮号,设备键,旧指纹,新指纹,生效时,说明) VALUES(?,?,?,?,?,'轮换生效')",
        (轮号, body.设备键, 旧, body.新指纹, ts),
    )
    c.execute(
        "UPDATE 设备册 SET 凭证指纹=?, 更新时=? WHERE 设备键=?",
        (body.新指纹, ts, body.设备键),
    )
    c.commit()
    c.close()
    return {"ok": True, "轮号": 轮号, "旧指纹": 旧, "新指纹": body.新指纹}


@api.get("/对影验")
def 对影验(设备键: str | None = None):
    c = 连接()
    if 设备键:
        设备们 = c.execute("SELECT * FROM 设备册 WHERE 设备键=?", (设备键,)).fetchall()
    else:
        设备们 = c.execute("SELECT * FROM 设备册 ORDER BY 设备键").fetchall()
    结果 = []
    for d in 设备们:
        键 = d["设备键"]
        影 = c.execute("SELECT * FROM 影子台 WHERE 设备键=?", (键,)).fetchone()
        在途 = c.execute(
            "SELECT COUNT(*) n FROM 指令廊 WHERE 设备键=? AND 状态='在途'", (键,)
        ).fetchone()["n"]
        积压 = c.execute(
            "SELECT COUNT(*) n FROM 补投条 WHERE 设备键=? AND 状态='积压'", (键,)
        ).fetchone()["n"]
        最近轮 = c.execute(
            "SELECT * FROM 凭证轮 WHERE 设备键=? ORDER BY 生效时 DESC LIMIT 1", (键,)
        ).fetchone()
        说明 = []
        ok = True
        if not 影 or 影["对齐态"] != "已齐":
            ok = False
            说明.append("影子未齐")
        if 在途 > 0:
            ok = False
            说明.append(f"仍有{在途}条在途")
        if 积压 > 0:
            ok = False
            说明.append(f"仍有{积压}条积压")
        if 最近轮 and 最近轮["新指纹"] != d["凭证指纹"]:
            ok = False
            说明.append("凭证轮与在册指纹不一致")
        if ok:
            说明.append("影子已齐 · 指令无在途积压 · 凭证一致")
        结果.append(
            {
                "设备键": 键,
                "别名": d["别名"],
                "通过": ok,
                "对齐态": 影["对齐态"] if 影 else "无",
                "在线": d["在线"],
                "凭证指纹": d["凭证指纹"],
                "说明": "；".join(说明),
            }
        )
    c.close()
    return 结果


@api.post("/演示/入册")
def 演示入册():
    data = _读预置("预置设备")
    return 写设备(设备入(**data))


@api.post("/演示/期望")
def 演示期望():
    data = _读预置("预置期望")
    return 写期望(期望入(**data))


@api.post("/演示/上报")
def 演示上报():
    data = _读预置("预置上报")
    return 写上报(上报入(**data))


@api.post("/演示/下发")
def 演示下发():
    data = _读预置("预置指令")
    return 下发指令(指令入(**data))


@api.post("/演示/对影闭环")
def 演示对影闭环():
    """0-1：入册 → 期望/上报对齐 → 在线送达 → 断线积压 → 重连补投 → 轮换后旧证拒令。"""
    设备 = _读预置("预置设备")
    写设备(设备入(**设备))
    键 = 设备["设备键"]
    写期望(期望入(**_读预置("预置期望")))
    写上报(上报入(**_读预置("预置上报")))
    直达 = 下发指令(指令入(**_读预置("预置指令")))
    断线(断线入(设备键=键))
    积压 = 下发指令(
        指令入(设备键=键, 动作="重启模组", 载荷={"delay_sec": 3})
    )
    补 = 重连补投(断线入(设备键=键))
    轮 = 轮换凭证(轮换入(设备键=键, 新指纹="fp-rotated-01"))
    拒 = 下发指令(
        指令入(
            设备键=键,
            动作="读配置",
            载荷={},
            凭证指纹=设备["凭证指纹"],
        )
    )
    验 = 对影验(设备键=键)
    return {
        "ok": True,
        "直达": 直达,
        "积压": 积压,
        "补投": 补,
        "轮换": 轮,
        "旧证拒令": 拒,
        "对影验": 验,
    }
