import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import 连接, 预置目录, 立即事务
from app.seed import 现在
from app.modules.期望版本钉 import (
    钉版策略,
    读最新策略,
    版源_下发钉版,
    版源_读最新,
    版本冲突,
    钉版不可核,
    归一策略,
    规范JSON,
    钉住当前期望,
    写版本史,
    核验令,
    补投执行载荷,
)

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
        # 期望版本史的创世票：v0 = {}，让 v0 钉版令也能同票回翻。
        写版本史(c, body.设备键, 0, {}, ts)
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
    for r in rows:
        钉 = c.execute(
            "SELECT 钉住期望版 AS v, COUNT(*) AS n FROM 指令廊 "
            "WHERE 设备键=? AND 钉住期望版>0 GROUP BY 钉住期望版 ORDER BY 钉住期望版",
            (r["设备键"],),
        ).fetchall()
        r["钉住版本"] = [x["v"] for x in 钉]
        r["钉住版本计数"] = {str(x["v"]): x["n"] for x in 钉}
    c.close()
    return rows


class 期望入(BaseModel):
    设备键: str
    期望载荷: dict = Field(default_factory=dict)
    # CAS：调用方基于某版改写时带上；与当前版不符即 409 失败闭。
    前置期望版: int | None = None
    基于期望版: int | None = None


@api.post("/影子台/期望")
def 写期望(body: 期望入):
    c = 连接()
    if not c.execute("SELECT 1 FROM 设备册 WHERE 设备键=?", (body.设备键,)).fetchone():
        c.close()
        raise HTTPException(400, "设备不在册")
    基准 = body.前置期望版 if body.前置期望版 is not None else body.基于期望版
    ts = 现在()
    try:
        with 立即事务(c):
            影 = c.execute(
                "SELECT * FROM 影子台 WHERE 设备键=?", (body.设备键,)
            ).fetchone()
            旧版 = int(影["期望版"]) if 影 else 0
            if 基准 is not None and int(基准) != 旧版:
                raise 版本冲突(
                    f"期望版本并发冲突：前置 v{基准} ≠ 当前 v{旧版}，失败闭未写入",
                    前置期望版=int(基准),
                    当前期望版=旧版,
                )
            期望文 = json.dumps(body.期望载荷, ensure_ascii=False, sort_keys=True)
            上报文 = 影["上报载荷"] if 影 else "{}"
            对齐 = "已齐" if 期望文 == 上报文 else "未齐"
            版 = 旧版 + 1 if 影 else 1
            c.execute(
                "INSERT INTO 影子台(设备键,期望载荷,上报载荷,对齐态,期望版,上报版,更新时) "
                "VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(设备键) DO UPDATE SET 期望载荷=excluded.期望载荷,对齐态=excluded.对齐态,"
                "期望版=excluded.期望版,更新时=excluded.更新时",
                (body.设备键, 期望文, 上报文, 对齐, 版, 影["上报版"] if 影 else 0, ts),
            )
            写版本史(c, body.设备键, 版, body.期望载荷, ts)
    except 版本冲突 as e:
        c.close()
        raise HTTPException(409, detail={"code": "期望版本冲突", **e.明细})
    c.close()
    return {"ok": True, "对齐态": 对齐, "期望版": 版, "当前期望版": 版}


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
    # 期望版本钉：默认“下发时钉版”；对照可显式取“读最新”。
    取版策略: str | None = None
    # 调用方所见的期望版（CAS），任一键名均可。
    基于期望版: int | None = None
    前置期望版: int | None = None
    钉住期望版: int | None = None


def _指令响应行(c, 令号: str) -> dict:
    r = c.execute("SELECT * FROM 指令廊 WHERE 令号=?", (令号,)).fetchone()
    return 行(r)


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
    策略 = 归一策略(body.取版策略)
    基准 = (
        body.基于期望版
        if body.基于期望版 is not None
        else body.前置期望版
        if body.前置期望版 is not None
        else body.钉住期望版
    )
    载荷文 = json.dumps(body.载荷, ensure_ascii=False)
    应答: dict | None = None

    try:
        with 立即事务(c):
            # 写事务内读影子当前版：钉版与影子台当前期望保证同票。
            钉 = 钉住当前期望(c, body.设备键, 基准)
            钉版号 = 钉["钉住期望版"]
            当前快照文 = 钉["期望快照"]
            快照文 = 当前快照文 if 策略 == 钉版策略 else ""
            核 = 钉["快照核"] if 策略 == 钉版策略 else ""
            版源 = 版源_下发钉版 if 策略 == 钉版策略 else ""
            # 读最新对照路径廊行“只存动作”：不钉版号、不存快照（列落 0/空）。
            存钉版 = 钉版号 if 策略 == 钉版策略 else 0

            if 指纹 != 设备["凭证指纹"]:
                c.execute(
                    "INSERT INTO 指令廊(令号,设备键,动作,载荷,状态,凭证指纹,下发时,闭环时,说明,"
                    "取版策略,钉住期望版,期望快照,快照核,版源,令源,执行期望版,执行载荷) "
                    "VALUES(?,?,?,?,'拒令',?,?,?,? ,?,?,?,?,?,? ,0,'')",
                    (
                        令号, body.设备键, body.动作, 载荷文, 指纹, ts, ts,
                        "凭证指纹与在册不符",
                        策略, 存钉版, 快照文, 核, 版源, "",
                    ),
                )
                应答 = {
                    "令号": 令号, "状态": "拒令", "说明": "凭证指纹与在册不符",
                    "钉住期望版": 存钉版, "当前期望版": 钉版号,
                    "版源": 版源 or 版源_读最新, "取版策略": 策略,
                }

            elif 设备["在线"] == "离线":
                c.execute(
                    "INSERT INTO 指令廊(令号,设备键,动作,载荷,状态,凭证指纹,下发时,说明,"
                    "取版策略,钉住期望版,期望快照,快照核,版源,令源,执行期望版,执行载荷) "
                    "VALUES(?,?,?,?,'在途',?,?,'离线积压' ,?,?,?,?,?,? ,0,'')",
                    (
                        令号, body.设备键, body.动作, 载荷文, 指纹, ts,
                        策略, 存钉版, 快照文, 核, 版源, "离线补投",
                    ),
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
                应答 = {
                    "令号": 令号, "状态": "在途", "说明": "离线积压", "条号": 条号,
                    "取版策略": 策略, "钉住期望版": 存钉版,
                    "钉住的期望版": 钉版号 if 策略 == 钉版策略 else None,
                    "当前期望版": 钉版号,
                    "期望快照": json.loads(快照文) if 快照文 else None,
                    "版源": 版源, "令源": "离线补投", "投递路径": "离线补投",
                }

            else:
                # 在线直达：同样钉版，并当场按钉版快照形成执行载荷（读最新对照除外）。
                if 策略 == 钉版策略:
                    执行版, 执行文, 执行源 = 钉版号, 当前快照文, 版源_下发钉版
                else:
                    # 读最新在直达当下读到的就是当前期望；钉() 已在同事务读得当前票。
                    执行版, 执行文, 执行源 = 钉版号, 当前快照文, 版源_读最新
                c.execute(
                    "INSERT INTO 指令廊(令号,设备键,动作,载荷,状态,凭证指纹,下发时,闭环时,说明,"
                    "取版策略,钉住期望版,期望快照,快照核,版源,令源,执行期望版,执行载荷) "
                    "VALUES(?,?,?,?,'送达',?,?,?,'在线直达' ,?,?,?,?,?,? ,?,?)",
                    (
                        令号, body.设备键, body.动作, 载荷文, 指纹, ts, ts,
                        策略, 存钉版, 快照文, 核, 执行源, "在线直达", 执行版, 执行文,
                    ),
                )
                应答 = {
                    "令号": 令号, "状态": "送达", "说明": "在线直达",
                    "取版策略": 策略, "钉住期望版": 存钉版,
                    "钉住的期望版": 钉版号 if 策略 == 钉版策略 else None,
                    "当前期望版": 钉版号,
                    "期望快照": json.loads(快照文) if 快照文 else None,
                    "执行期望版": 执行版,
                    "执行载荷": json.loads(执行文),
                    "版源": 执行源, "令源": "在线直达", "投递路径": "在线直达",
                }
    except 版本冲突 as e:
        c.close()
        raise HTTPException(409, detail={"code": "期望版本冲突", **e.明细})
    c.close()
    return 应答


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
    完成: list[str] = []
    执行明细: list[dict] = []
    try:
        with 立即事务(c):
            c.execute(
                "UPDATE 设备册 SET 在线='在线', 更新时=? WHERE 设备键=?",
                (ts, body.设备键),
            )
            条们 = c.execute(
                "SELECT * FROM 补投条 WHERE 设备键=? AND 状态='积压' ORDER BY 序",
                (body.设备键,),
            ).fetchall()
            for 条 in 条们:
                令 = c.execute(
                    "SELECT * FROM 指令廊 WHERE 令号=?", (条["令号"],)
                ).fetchone()
                if 令 is None or 令["状态"] != "在途":
                    # 已被别处闭环：条目标已补，幂等跳过。
                    c.execute(
                        "UPDATE 补投条 SET 状态='已补', 补投时=? WHERE 条号=?",
                        (ts, 条["条号"]),
                    )
                    continue
                # 关键：钉版按廊行快照执行；读最新在此刻事务内读当前期望。
                # 钉版校验不过直接抛错 → 整个补投事务回滚，令仍在途/条仍积压（失败闭）。
                执行版, 执行文, 执行源 = 补投执行载荷(c, 令)
                c.execute(
                    "UPDATE 补投条 SET 状态='已补', 补投时=? WHERE 条号=?",
                    (ts, 条["条号"]),
                )
                新说明 = "重连补投·按钉版快照执行" if 执行源 == 版源_下发钉版 else "重连补投·执行时读最新"
                c.execute(
                    "UPDATE 指令廊 SET 状态='送达', 闭环时=?, 说明=?, 版源=?, "
                    "执行期望版=?, 执行载荷=? WHERE 令号=? AND 状态='在途'",
                    (ts, 新说明, 执行源, 执行版, 执行文, 条["令号"]),
                )
                完成.append(条["令号"])
                执行明细.append(
                    {
                        "令号": 条["令号"],
                        "执行期望版": 执行版,
                        "版源": 执行源,
                        "执行载荷": json.loads(执行文),
                    }
                )
    except 钉版不可核 as e:
        c.close()
        raise HTTPException(409, detail={"code": "钉版校验失败闭", **e.明细, "问题": e.消息})
    c.close()
    return {"ok": True, "补投数": len(完成), "令号": 完成, "执行": 执行明细}


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
        # 期望版本钉：版漂（钉 v1 / 当前 v2）只是事实，不判失败；
        # 只有钉版令缺快照、被篡改、执行漂版才记为钉版异常。
        令们 = c.execute(
            "SELECT * FROM 指令廊 WHERE 设备键=? ORDER BY 下发时 DESC LIMIT 100", (键,)
        ).fetchall()
        版漂令数 = 0
        钉版异常 = []
        for 令 in 令们:
            if (令["钉住期望版"] or 0) and 影 and 令["钉住期望版"] != 影["期望版"]:
                版漂令数 += 1
            if 归一策略(令["取版策略"]) == 钉版策略:
                try:
                    r = 核验令(c, 令)
                    if not r["valid"]:
                        钉版异常.append({"令号": 令["令号"], "问题": r["核验说明"]})
                except HTTPException:
                    raise
                except Exception as e:  # 核验本身出错也按不可核处理
                    钉版异常.append({"令号": 令["令号"], "问题": str(e)})
        说明 = []
        ok = True
        if not 影 or 影["对齐态"] != "已齐":
            ok = False
            说明.append("影子未齐（以当前期望版为准，不拿钉住旧版误判已齐）")
        if 在途 > 0:
            ok = False
            说明.append(f"仍有{在途}条在途")
        if 积压 > 0:
            ok = False
            说明.append(f"仍有{积压}条积压")
        if 钉版异常:
            ok = False
            说明.append(f"{len(钉版异常)}条令钉版不可核（失败闭）")
        if 最近轮 and 最近轮["新指纹"] != d["凭证指纹"]:
            ok = False
            说明.append("凭证轮与在册指纹不一致")
        if ok:
            尾 = f"；{版漂令数}条令钉住旧版、当前期望v{影['期望版'] if 影 else 0}（版漂不误报）" if 版漂令数 else ""
            说明.append("影子已齐 · 指令无在途积压 · 钉版可核 · 凭证一致" + 尾)
        结果.append(
            {
                "设备键": 键,
                "别名": d["别名"],
                "通过": ok,
                "对齐态": 影["对齐态"] if 影 else "无",
                "在线": d["在线"],
                "凭证指纹": d["凭证指纹"],
                "当前期望版": 影["期望版"] if 影 else 0,
                "上报版": 影["上报版"] if 影 else 0,
                "版漂令数": 版漂令数,
                "钉版异常令数": len(钉版异常),
                "钉版异常": 钉版异常,
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


# ============================ 期望版本钉：核验口 / 令册 / 场景自动化 ============================

def _核验或404(令号: str) -> dict:
    c = 连接()
    令 = c.execute("SELECT * FROM 指令廊 WHERE 令号=?", (令号,)).fetchone()
    if 令 is None:
        c.close()
        raise HTTPException(404, f"无此令号：{令号}")
    out = 核验令(c, 令)
    c.close()
    return out


@api.get("/期望版本钉/核验")
@api.get("/期望版本钉/核验口")
@api.get("/期望版本钉/verify")
@api.get("/版本钉/核验")
@api.get("/核验")
@api.get("/指令廊/核验")
def 钉版核验口(
    令号: str | None = None,
    cmd: str | None = None,
    id: str | None = None,
    order: str | None = None,
):
    号 = 令号 or cmd or id or order
    if not 号:
        raise HTTPException(400, "必须给令号（?令号=CMD-...）")
    return _核验或404(号)


@api.get("/期望版本钉/令号/{cmd}")
@api.get("/期望版本钉/{cmd}/核验")
@api.get("/指令廊/{cmd}/核验")
def 钉版核验路径(cmd: str):
    # 路径占位符必须 ASCII（Starlette PARAM_RE 不收中文参数名）；对外语义仍是令号。
    return _核验或404(cmd)


_令册SQL = (
    "SELECT g.*, s.期望版 AS 当前期望版, s.对齐态 AS 影子对齐态 "
    "FROM 指令廊 g LEFT JOIN 影子台 s ON s.设备键 = g.设备键 "
)


@api.get("/期望版本钉")
@api.get("/期望版本钉/令册")
def 钉版令册(令号: str | None = None, 设备键: str | None = None):
    c = 连接()
    where, args = [], []
    if 令号:
        where.append("g.令号=?")
        args.append(令号)
    if 设备键:
        where.append("g.设备键=?")
        args.append(设备键)
    sql = _令册SQL
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY g.下发时 DESC LIMIT 200"
    rows = [行(r) for r in c.execute(sql, args).fetchall()]
    c.close()
    return rows


@api.post("/期望版本钉/下发")
def 钉版下发别名(body: 指令入):
    """钉版命名空间下的下发别名；默认策略仍是下发时钉版。"""
    if not body.取版策略:
        body.取版策略 = 钉版策略
    return 下发指令(body)


@api.post("/期望版本钉/重连补投")
def 钉版补投别名(body: 断线入):
    return 重连补投(body)


class 场景入(BaseModel):
    设备键: str | None = None


def _断言(名: str, 实际, 期望=None, 通过: bool | None = None) -> dict:
    ok = (实际 == 期望) if 通过 is None else 通过
    return {"名": 名, "通过": bool(ok), "期望": 期望, "实际": 实际}


def _新场景键(prefix: str = "dev-pin") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@api.post("/期望版本钉/场景/钉旧版")
@api.post("/期望版本钉/自动化/钉旧版")
@api.post("/期望版本钉/场景/离线抬版再补投")
def 场景钉旧版(body: 场景入 | None = None):
    """规格主场景：写期望 v1 → 离线下发（钉 v1）→ 抬期望 v2 → 重连补投按 v1 执行。

    同设备再走一条在线直达钉版令，断言两条钉版路径的版源。
    """
    键 = (body.设备键 if body and body.设备键 else None) or _新场景键()
    v1 = {"mark": "v1", "freq_hz": 10, "firmware": "1.4.0"}
    v2 = {"mark": "v2", "freq_hz": 20, "firmware": "2.0.0"}
    写设备(设备入(设备键=键, 别名="钉旧版场景机", 凭证指纹="fp-init"))
    期1 = 写期望(期望入(设备键=键, 期望载荷=v1))
    断线(断线入(设备键=键))
    下发 = 下发指令(指令入(设备键=键, 动作="应用期望", 取版策略=钉版策略))
    离线令号 = 下发["令号"]
    期2 = 写期望(期望入(设备键=键, 期望载荷=v2))
    补 = 重连补投(断线入(设备键=键))
    核 = _核验或404(离线令号)

    # 在线直达路径：重连后设备在线，再发一条，仍须钉版并留版源。
    直达 = 下发指令(指令入(设备键=键, 动作="在线应用", 取版策略=钉版策略))
    在线令号 = 直达["令号"]
    在线核 = _核验或404(在线令号)

    断言 = [
        _断言("v1 写入后期望版=1", 期1["期望版"], 1),
        _断言("抬版后期望版=2", 期2["期望版"], 2),
        _断言("离线令钉住的期望版=1", 核["钉住的期望版"], 1),
        _断言("核验口当前期望版=2", 核["当前期望版"], 2),
        _断言("补投执行载荷属于 v1（旧版）", 核["执行载荷"], v1),
        _断言("执行载荷不是 v2", 核["执行载荷"] != v2, True),
        _断言("执行期望版=钉住版=1", 核["执行期望版"], 1),
        _断言("版源=下发时钉版", 核["版源"], 版源_下发钉版),
        _断言("令源=离线补投", 核["令源"], "离线补投"),
        _断言("版漂标记=true（钉1当前2）", 核["版漂"], True),
        _断言("valid=true（版漂不误报）", 核["valid"], True),
        _断言("快照与期望版本史同票", 核["同票"], True),
        _断言("补投响应回传 1 条执行明细", len(补.get("执行", [])), 1),
        _断言("在线直达令留下版源字段", 在线核["版源"], 版源_下发钉版),
        _断言("在线直达令源=在线直达", 在线核["令源"], "在线直达"),
        _断言("在线直达钉当前版2且执行 v2", 在线核["执行载荷"], v2),
        _断言("在线直达 valid=true", 在线核["valid"], True),
    ]
    return {
        "ok": all(a["通过"] for a in 断言),
        "全部通过": all(a["通过"] for a in 断言),
        "设备键": 键,
        "离线令号": 离线令号,
        "在线令号": 在线令号,
        "v1载荷": v1,
        "v2载荷": v2,
        "核验": 核,
        "在线核验": 在线核,
        "补投": 补,
        "断言": 断言,
    }


@api.post("/期望版本钉/场景/读最新")
@api.post("/期望版本钉/自动化/读最新")
def 场景读最新(body: 场景入 | None = None):
    """对照路径：廊行只存动作不存快照，补投当下读当前期望 → 执行 v2。"""
    键 = (body.设备键 if body and body.设备键 else None) or _新场景键("dev-latest")
    v1 = {"mark": "v1", "freq_hz": 10}
    v2 = {"mark": "v2", "freq_hz": 20}
    写设备(设备入(设备键=键, 别名="读最新对照机", 凭证指纹="fp-init"))
    写期望(期望入(设备键=键, 期望载荷=v1))
    断线(断线入(设备键=键))
    下发 = 下发指令(指令入(设备键=键, 动作="应用期望", 取版策略=读最新策略))
    令号 = 下发["令号"]
    在途核 = _核验或404(令号)
    写期望(期望入(设备键=键, 期望载荷=v2))
    补 = 重连补投(断线入(设备键=键))
    核 = _核验或404(令号)

    断言 = [
        _断言("在途廊行不钉版号（钉住的期望版=null）", 在途核["钉住的期望版"], None),
        _断言("在途廊行无期望快照（只存动作）", 在途核["期望快照"], None),
        _断言("在途读最新令 valid=false（无钉版凭证，对照）", 在途核["valid"], False),
        _断言("补投执行载荷漂到 v2（最新）", 核["执行载荷"], v2),
        _断言("执行期望版=2", 核["执行期望版"], 2),
        _断言("版源=执行时读最新", 核["版源"], 版源_读最新),
        _断言("令源=离线补投", 核["令源"], "离线补投"),
        _断言("送达后执行痕迹可核 valid=true", 核["valid"], True),
        _断言("与钉旧版相反：不执行 v1", 核["执行载荷"] != v1, True),
    ]
    return {
        "ok": all(a["通过"] for a in 断言),
        "全部通过": all(a["通过"] for a in 断言),
        "设备键": 键,
        "令号": 令号,
        "在途核验": 在途核,
        "核验": 核,
        "补投": 补,
        "断言": 断言,
    }


@api.post("/期望版本钉/场景/并发失败闭")
def 场景并发失败闭():
    """CAS 并发抬版：同一前置版的 N 个并发改写恰一个成功，其余 409 失败闭；

    另演示快照被篡改后补投被拒（令留在途）。
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    键 = _新场景键("dev-race")
    v1 = {"mark": "v1", "freq_hz": 10}
    写设备(设备入(设备键=键, 别名="并发失败闭机", 凭证指纹="fp-init"))
    写期望(期望入(设备键=键, 期望载荷=v1))
    断线(断线入(设备键=键))
    下发 = 下发指令(指令入(设备键=键, 动作="应用期望"))
    令号 = 下发["令号"]

    n = 8
    闸 = threading.Barrier(n)

    def 抢写(i: int):
        闸.wait()
        try:
            r = 写期望(
                期望入(
                    设备键=键,
                    期望载荷={"mark": f"race-{i}"},
                    前置期望版=1,
                )
            )
            return ("ok", r.get("期望版"))
        except HTTPException as e:
            return ("conflict", e.status_code)
        except Exception as e:  # noqa: BLE001 - 演练要把任何意外带回断言
            return ("error", repr(e))

    with ThreadPoolExecutor(max_workers=n) as pool:
        结果 = list(pool.map(抢写, range(n)))
    成功 = [r for r in 结果 if r[0] == "ok"]
    冲突 = [r for r in 结果 if r[0] == "conflict"]
    意外 = [r for r in 结果 if r[0] == "error"]

    # 竞争结束后补投：钉版令仍须按 v1 执行且 valid。
    补 = 重连补投(断线入(设备键=键))
    核 = _核验或404(令号)

    # 篡改快照 → 另造一台设备演示补投失败闭。
    键2 = _新场景键("dev-tamper")
    写设备(设备入(设备键=键2, 别名="篡改闭闸机", 凭证指纹="fp-init"))
    写期望(期望入(设备键=键2, 期望载荷=v1))
    断线(断线入(设备键=键2))
    恶令 = 下发指令(指令入(设备键=键2, 动作="应用期望"))
    恶号 = 恶令["令号"]
    cc = 连接()
    cc.execute(
        "UPDATE 指令廊 SET 期望快照=? WHERE 令号=?",
        (json.dumps({"mark": "被篡改"}), 恶号),
    )
    cc.commit()
    cc.close()
    篡改闭 = None
    try:
        重连补投(断线入(设备键=键2))
    except HTTPException as e:
        篡改闭 = e.status_code
    篡改后 = _核验或404(恶号)

    断言 = [
        _断言(f"{n} 个同基并发抬版恰 1 个成功", len(成功), 1),
        _断言("其余全部 409 冲突失败闭", len(冲突), n - 1),
        _断言("无 500/意外错误", len(意外), 0),
        _断言("竞争后钉版补投仍执行 v1", 核["执行载荷"], v1),
        _断言("竞争后钉版 valid=true", 核["valid"], True),
        _断言("篡改快照补投被 409 拒绝", 篡改闭, 409),
        _断言("篡改令仍未送达（valid=false）", 篡改后["valid"], False),
        _断言("篡改令状态留在途", 篡改后["状态"], "在途"),
    ]
    return {
        "ok": all(a["通过"] for a in 断言),
        "全部通过": all(a["通过"] for a in 断言),
        "设备键": 键,
        "令号": 令号,
        "并发结果": 结果,
        "成功数": len(成功),
        "冲突数": len(冲突),
        "意外": 意外,
        "核验": 核,
        "篡改令号": 恶号,
        "篡改拒绝状态": 篡改闭,
        "篡改核验": 篡改后,
        "断言": 断言,
    }
