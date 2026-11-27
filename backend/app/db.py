import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

数据目录 = Path(os.environ.get("数据目录", Path(__file__).resolve().parent.parent / "data"))
预置目录 = Path(
    os.environ.get("预置目录")
    or os.environ.get("样例目录")
    or (Path(__file__).resolve().parent.parent.parent / "fixtures")
)
库路径 = 数据目录 / "影湾.db"


def 连接() -> sqlite3.Connection:
    数据目录.mkdir(parents=True, exist_ok=True)
    # timeout + busy_timeout：改期望与补投并发时写锁排队，而不是立刻 database is locked。
    c = sqlite3.connect(库路径, timeout=10.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA busy_timeout = 10000")
    return c


@contextmanager
def 立即事务(c: sqlite3.Connection):
    """串行化复合写：拿到写锁后再读当前期望，保证钉住的版号/快照与影子台同票。"""
    c.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        c.execute("ROLLBACK")
        raise
    else:
        c.execute("COMMIT")
