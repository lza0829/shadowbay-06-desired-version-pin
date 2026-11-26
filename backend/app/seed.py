from datetime import datetime, timezone

from app.db import 连接

STUBS = [
    "影子冲突仲裁",
    "指令幂等键",
    "在途超时作废",
    "补投序缺口",
    "凭证宽限期",
    "期望版本钉",
    "上报晚到",
    "多端共册",
    "网关代理转发",
    "指令优先级插队",
    "离线容量闸",
    "影子部分对齐",
    "轮换双持窗",
    "补投失败隔离",
    "设备吊销涟漪",
    "遥测旁路",
    "指令回执分叉",
    "期望回滚",
    "指纹吊销清单",
    "边缘缓冲溢出",
]

建表 = """
CREATE TABLE IF NOT EXISTS 设备册 (
  设备键 TEXT PRIMARY KEY,
  别名 TEXT NOT NULL,
  在线 TEXT NOT NULL DEFAULT '离线',
  凭证指纹 TEXT NOT NULL,
  入册时 TEXT NOT NULL,
  更新时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 影子台 (
  设备键 TEXT PRIMARY KEY,
  期望载荷 TEXT NOT NULL DEFAULT '{}',
  上报载荷 TEXT NOT NULL DEFAULT '{}',
  对齐态 TEXT NOT NULL DEFAULT '未齐',
  期望版 INTEGER NOT NULL DEFAULT 0,
  上报版 INTEGER NOT NULL DEFAULT 0,
  更新时 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS 指令廊 (
  令号 TEXT PRIMARY KEY,
  设备键 TEXT NOT NULL,
  动作 TEXT NOT NULL,
  载荷 TEXT NOT NULL DEFAULT '{}',
  状态 TEXT NOT NULL DEFAULT '在途',
  凭证指纹 TEXT NOT NULL DEFAULT '',
  下发时 TEXT NOT NULL,
  闭环时 TEXT NOT NULL DEFAULT '',
  说明 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 补投条 (
  条号 TEXT PRIMARY KEY,
  设备键 TEXT NOT NULL,
  令号 TEXT NOT NULL,
  序 INTEGER NOT NULL,
  状态 TEXT NOT NULL DEFAULT '积压',
  入条时 TEXT NOT NULL,
  补投时 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 凭证轮 (
  轮号 TEXT PRIMARY KEY,
  设备键 TEXT NOT NULL,
  旧指纹 TEXT NOT NULL,
  新指纹 TEXT NOT NULL,
  生效时 TEXT NOT NULL,
  说明 TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS 空桩 (
  名 TEXT PRIMARY KEY,
  状态 TEXT NOT NULL DEFAULT '空桩'
);
"""


def 现在() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def 初始化库() -> None:
    c = 连接()
    c.executescript(建表)
    c.execute("DELETE FROM 空桩")
    c.executemany("INSERT INTO 空桩(名, 状态) VALUES (?, ?)", [(s, "空桩") for s in STUBS])
    c.commit()
    c.close()
