"""期望版本钉（空桩落地）。

两条互斥路径：

- 下发时钉版（默认、硬约束路径）：令廊行保存「钉住期望版」号 + 「期望快照」JSON
  （含快照核），送达/离线补投一律按快照执行；在途期间期望再抬版也不漂。
- 执行时读最新（仅作对照）：在途廊行只存动作、不存快照；送达当下才读影子台当前
  期望并拼出执行载荷，同时留下「执行期望版 + 执行载荷」痕迹与版源。

核验口按令号回翻：令号 / 钉住的期望版 / 当前期望版 / 执行载荷 / valid，
并给出快照核、期望版本史同票校验。版漂（钉 v1、当前 v2）是预期事实，
不单独构成 invalid；缺钉版、快照被篡改、执行载荷与钉版不一致才失败闭。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

钉版策略 = "钉版"
读最新策略 = "读最新"

版源_下发钉版 = "下发时钉版"
版源_读最新 = "执行时读最新"

# 入参里可能出现的英文/别名归一到两条互斥路径。
_策略别名 = {
    "钉版": 钉版策略,
    "钉住": 钉版策略,
    "pin": 钉版策略,
    "pinned": 钉版策略,
    "snapshot": 钉版策略,
    "读最新": 读最新策略,
    "最新": 读最新策略,
    "latest": 读最新策略,
    "head": 读最新策略,
}


class 版本冲突(Exception):
    """CAS / 钉版基准与当前期望版不一致 —— 调用方应映射为 409 失败闭。"""

    def __init__(self, 消息: str, **明细: Any):
        super().__init__(消息)
        self.消息 = 消息
        self.明细 = 明细


class 钉版不可核(Exception):
    """令廊行缺钉版/快照或快照核、同票校验失败 —— 送达必须失败闭。"""

    def __init__(self, 消息: str, **明细: Any):
        super().__init__(消息)
        self.消息 = 消息
        self.明细 = 明细


def 规范JSON(载荷: Any) -> str:
    """快照/哈希/同票比对统一用规范化 JSON（键排序、无空白、不转义中文）。"""
    return json.dumps(载荷, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def 解析JSON(文: str | None, 默认: Any = None) -> Any:
    if 文 is None or 文 == "":
        return 默认
    try:
        return json.loads(文)
    except (json.JSONDecodeError, TypeError):
        return 默认


def 快照核(快照文: str) -> str:
    return "sha256:" + hashlib.sha256(快照文.encode("utf-8")).hexdigest()[:16]


def 归一策略(v: Any) -> str:
    if v is None:
        return 钉版策略
    return _策略别名.get(str(v).strip().lower(), _策略别名.get(str(v).strip(), 钉版策略))


def 读当前期望(c: sqlite3.Connection, 设备键: str) -> tuple[int, dict[str, Any]]:
    """返回 (当前期望版, 期望载荷对象)。设备入册时必建影子行（v0, {}）。"""
    影 = c.execute("SELECT 期望版, 期望载荷 FROM 影子台 WHERE 设备键=?", (设备键,)).fetchone()
    if 影 is None:
        return 0, {}
    return int(影["期望版"] or 0), (解析JSON(影["期望载荷"], {}) or {})


def 写版本史(c: sqlite3.Connection, 设备键: str, 版: int, 载荷: Any, 时: str) -> None:
    文 = 规范JSON(载荷)
    c.execute(
        "INSERT OR IGNORE INTO 期望版本史(设备键, 期望版, 期望载荷, 写时) VALUES(?,?,?,?)",
        (设备键, 版, 文, 时),
    )


def 取版本史(c: sqlite3.Connection, 设备键: str, 版: int) -> dict[str, Any] | None:
    行 = c.execute(
        "SELECT * FROM 期望版本史 WHERE 设备键=? AND 期望版=?", (设备键, 版)
    ).fetchone()
    return dict(行) if 行 else None


def 钉住当前期望(
    c: sqlite3.Connection,
    设备键: str,
    基准期望版: int | None = None,
) -> dict[str, Any]:
    """下发时钉版：必须在 BEGIN IMMEDIATE 事务内调用。

    若调用方带了基准期望版（CAS / 页面所见版本），与库内当前版不一致即失败闭，
    绝不把令钉到一个自己没见过的版本上。
    """
    版, 载荷 = 读当前期望(c, 设备键)
    if 基准期望版 is not None and int(基准期望版) != 版:
        raise 版本冲突(
            f"期望版本漂移：基准 v{基准期望版}，当前 v{版}，已失败闭拒发",
            基准期望版=int(基准期望版),
            当前期望版=版,
        )
    快照 = 规范JSON(载荷)
    return {
        "钉住期望版": 版,
        "期望快照": 快照,
        "快照核": 快照核(快照),
        "当前期望版": 版,
    }


def 校验钉版记录(c: sqlite3.Connection, 令: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """核验一条令的钉版留痕与期望版本史是否同票。返回检查项明细。"""
    d = dict(令)
    令号 = d["令号"]
    设备键 = d["设备键"]
    策略 = 归一策略(d.get("取版策略"))
    钉版 = int(d.get("钉住期望版") or 0)
    快照文 = d.get("期望快照") or ""
    核 = d.get("快照核") or ""
    执行版 = int(d.get("执行期望版") or 0)
    执行文 = d.get("执行载荷") or ""
    状态 = d.get("状态")

    检查: dict[str, Any] = {
        "策略": 策略,
        "有钉版号": 钉版 > 0 or 快照文 != "",
        "有快照": bool(快照文),
        "快照核一致": False,
        "版本史同票": False,
        "执行合钉": False,
    }
    问题: list[str] = []

    快照obj = 解析JSON(快照文, None) if 快照文 else None
    if 快照文:
        检查["快照可解析"] = 快照obj is not None
        if 快照obj is None:
            问题.append("期望快照不是合法 JSON")
        else:
            期望核 = 快照核(快照文)
            检查["快照核一致"] = (not 核) or 核 == 期望核
            if not 检查["快照核一致"]:
                问题.append(f"快照核不符：廊行 {核} ≠ 重算 {期望核}（快照可能被篡改）")
            史 = 取版本史(c, 设备键, 钉版)
            if 史 is None and 钉版 == 0:
                # v0 创世期望 {}：设备入册即有影子行，允许无独立史行。
                检查["版本史同票"] = 快照obj == {}
            elif 史 is not None:
                检查["版本史同票"] = 解析JSON(史["期望载荷"]) == 快照obj
            if not 检查["版本史同票"]:
                问题.append(f"快照与期望版本史 v{钉版} 不同票")

    执行obj = 解析JSON(执行文, None) if 执行文 else None
    if 执行文:
        检查["执行载荷可解析"] = 执行obj is not None

    if 策略 == 钉版策略:
        if not 快照文:
            问题.append("禁止只存动作名无快照：钉版令缺少期望快照")
        if 状态 == "送达":
            if not 执行文 or 执行obj is None:
                问题.append("已送达但无执行载荷留痕")
            else:
                检查["执行合钉"] = (执行版 == 钉版) and (执行obj == 快照obj)
                if not 检查["执行合钉"]:
                    问题.append(
                        f"执行载荷漂版：执行源 v{执行版}，钉住 v{钉版}，或载荷与快照不一致"
                    )
        else:
            # 在途/拒令：尚未产生执行事实；钉版记录本身可核即可。
            检查["执行合钉"] = True
    else:
        # 读最新对照路径：送达前允许无钉版；送达后执行痕迹必须与版本史同票。
        if 状态 == "送达":
            if not 执行文 or 执行obj is None:
                问题.append("读最新令已送达但未留下执行载荷")
            else:
                史 = 取版本史(c, 设备键, 执行版)
                检查["执行版可溯"] = 史 is not None or (执行版 == 0 and 执行obj == {})
                if 史 is not None:
                    检查["执行版可溯"] = 解析JSON(史["期望载荷"]) == 执行obj
                if not 检查["执行版可溯"]:
                    问题.append(f"执行载荷与送达时读到的当前期望 v{执行版} 不同票")
                检查["执行合钉"] = bool(检查["执行版可溯"])
        else:
            检查["对照路径待送达"] = True
            检查["执行合钉"] = True

    当前版, _ = 读当前期望(c, 设备键)
    版漂 = (钉版 > 0 or 快照文 != "") and 钉版 != 当前版

    if 策略 == 钉版策略:
        valid = not 问题
    else:
        # 对照路径：送达后按执行痕迹核验；在途无快照本身不可作为钉版凭证。
        valid = not 问题 and (状态 == "送达")

    return {
        "令号": 令号,
        "设备键": 设备键,
        "动作": d.get("动作"),
        "状态": 状态,
        "取版策略": 策略,
        # 规格要求的五个核验字段（长名 + 短名双给）。
        "钉住的期望版": 钉版 if 检查["有钉版号"] else None,
        "钉住期望版": 钉版,
        "当前期望版": 当前版,
        "执行载荷": 执行obj,
        "valid": valid,
        "有效": valid,
        "版源": d.get("版源") or (版源_下发钉版 if 策略 == 钉版策略 else 版源_读最新),
        "令源": d.get("令源") or "",
        "执行期望版": 执行版 or None,
        "期望快照": 快照obj,
        "快照核": 核,
        "版漂": 版漂,
        "同票": 检查.get("版本史同票", False) if 策略 == 钉版策略 else 检查.get("执行版可溯", False),
        "检查项": 检查,
        "问题": 问题,
        "核验说明": "；".join(问题)
        or (
            f"钉版 v{钉版} 可核，执行按快照，当前期望 v{当前版}"
            + ("（版漂为预期，不误判）" if 版漂 else "")
            if 策略 == 钉版策略
            else f"读最新对照：执行源 v{执行版 or 当前版}"
        ),
    }


def 补投执行载荷(c: sqlite3.Connection, 令: sqlite3.Row) -> tuple[int, str, str]:
    """重连补投/送达当下解析真正要执行的载荷。

    钉版路径：只认廊行快照并做快照核 + 版本史同票校验，任何不过 → 钉版不可核（失败闭）。
    读最新路径：在补投事务内读当前影子期望，返回当前版载荷。
    """
    d = dict(令)
    策略 = 归一策略(d.get("取版策略"))
    if 策略 == 读最新策略:
        版, obj = 读当前期望(c, d["设备键"])
        return 版, 规范JSON(obj), 版源_读最新

    钉版 = int(d.get("钉住期望版") or 0)
    快照文 = d.get("期望快照") or ""
    核 = d.get("快照核") or ""
    if not 快照文:
        raise 钉版不可核("令廊行无期望快照，拒绝送达（禁止只存动作名无快照）", 令号=d["令号"])
    obj = 解析JSON(快照文, None)
    if obj is None:
        raise 钉版不可核("期望快照 JSON 损坏，失败闭", 令号=d["令号"])
    if 核 and 核 != 快照核(快照文):
        raise 钉版不可核("快照核不一致，快照或被篡改，失败闭", 令号=d["令号"])
    史 = 取版本史(c, d["设备键"], 钉版)
    if 史 is None:
        if not (钉版 == 0 and obj == {}):
            raise 钉版不可核(
                f"期望版本史缺 v{钉版}，无法同票核验，失败闭", 令号=d["令号"]
            )
    elif 解析JSON(史["期望载荷"]) != obj:
        raise 钉版不可核("快照与期望版本史不同票，失败闭", 令号=d["令号"])
    return 钉版, 快照文, 版源_下发钉版


# 路由/核验口使用的短名别名。
核验令 = 校验钉版记录
