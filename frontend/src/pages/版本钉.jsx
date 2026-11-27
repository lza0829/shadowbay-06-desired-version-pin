import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";
import { 核验卡, 令号回翻, 断言清单, 版源徽 } from "../钉版件.jsx";

const 场景 = [
  {
    key: "pin",
    ep: "/期望版本钉/场景/钉旧版",
    钮: "自动化 A · 离线下发→抬版→补投（钉旧版 v1）",
    cls: "主钮",
    述: "写期望 v1；离线下发并钉 v1 快照；在途抬期望 v2；重连补投仍按 v1 执行。同场景另验一条在线直达钉版令。",
  },
  {
    key: "latest",
    ep: "/期望版本钉/场景/读最新",
    钮: "自动化 B · 读最新对照（补投执行 v2）",
    cls: "铜钮",
    述: "互斥对照路径：廊行只存动作不存快照，补投当下读当前期望，执行载荷漂到 v2，版源=执行时读最新。",
  },
  {
    key: "race",
    ep: "/期望版本钉/场景/并发失败闭",
    钮: "并发失败闭演练（CAS 抢写 + 篡改快照）",
    cls: "铜钮",
    述: "同一前置版的 8 个并发抬版恰一个成功，其余 409；篡改快照后补投被 409 拒绝、令留在途。",
  },
];

function 载荷摘({ s }) {
  if (!s) return <span className="淡">—</span>;
  try {
    const o = typeof s === "string" ? JSON.parse(s) : s;
    return <code className="载荷摘">{JSON.stringify(o)}</code>;
  } catch {
    return <code className="载荷摘">{String(s)}</code>;
  }
}

export default function 版本钉() {
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState("");
  const [results, setResults] = useState({});
  const [err, setErr] = useState("");
  const [focus, setFocus] = useState(null);

  const 刷 = () => get("/期望版本钉/令册").then(setRows).catch((e) => setErr(String(e.message || e)));
  useEffect(() => {
    刷();
  }, []);

  async function 跑(sc) {
    setBusy(sc.key);
    setErr("");
    try {
      const j = await post(sc.ep, {});
      setResults((m) => ({ ...m, [sc.key]: j }));
      await 刷();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy("");
    }
  }

  async function 核行(号) {
    try {
      const v = await get("/期望版本钉/核验?令号=" + encodeURIComponent(号));
      setFocus(v);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  return (
    <div>
      <h2 className="题">期望版本钉</h2>
      <p className="述">
        指令在途、期望又改版时，禁止执行载荷随意漂版。默认「下发时钉版」：廊行保存
        <b className="铜字"> 钉住期望版号 + 期望快照 JSON + 快照核 + 版源</b>
        ，在线直达与离线补投都按快照执行；「执行时读最新」仅作互斥对照。核验口按令号回翻，给出
        令号、钉住的期望版、当前期望版、执行载荷、valid。
      </p>

      <div className="场列">
        {场景.map((sc) => (
          <section className="场卡" key={sc.key}>
            <button className={sc.cls} disabled={busy === sc.key} onClick={() => 跑(sc)}>
              {busy === sc.key ? "执行中…" : sc.钮}
            </button>
            <p className="淡" style={{ margin: "0.6rem 0 0", fontSize: "0.85rem", lineHeight: 1.5 }}>
              {sc.述}
            </p>
          </section>
        ))}
      </div>
      {err && <p className="坏 讯">{err}</p>}

      {results.pin && (
        <section className="结果区">
          <h3 className="小节">A · 钉旧版结果（含在线直达）</h3>
          <断言清单 list={results.pin.断言} />
          <div className="双卡">
            <核验卡 v={results.pin.核验} />
            <核验卡 v={results.pin.在线核验} />
          </div>
        </section>
      )}
      {results.latest && (
        <section className="结果区">
          <h3 className="小节">B · 读最新对照结果</h3>
          <断言清单 list={results.latest.断言} />
          <核验卡 v={results.latest.核验} />
        </section>
      )}
      {results.race && (
        <section className="结果区">
          <h3 className="小节">并发失败闭结果</h3>
          <断言清单 list={results.race.断言} />
          {results.race.核验 && <核验卡 v={results.race.核验} />}
        </section>
      )}

      <section className="结果区">
        <h3 className="小节">按令号回翻</h3>
        <令号回翻 />
        {focus && <核验卡 v={focus} onClose={() => setFocus(null)} />}
      </section>

      <section className="结果区">
        <div className="行" style={{ justifyContent: "space-between" }}>
          <h3 className="小节" style={{ margin: 0 }}>钉版列 ⇄ 当前期望版 同屏对照（令册）</h3>
          <button onClick={刷}>刷新令册</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>令号</th>
              <th>设备</th>
              <th>状态</th>
              <th>钉住期望版</th>
              <th>当前期望版</th>
              <th>版源</th>
              <th>执行版</th>
              <th>执行载荷</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const 漂 = r.钉住期望版 > 0 && r.当前期望版 != null && r.钉住期望版 !== r.当前期望版;
              return (
                <tr key={r.令号} className={漂 ? "行漂" : ""}>
                  <td><code>{r.令号}</code></td>
                  <td className="淡">{r.设备键}</td>
                  <td className={r.状态 === "送达" ? "好" : r.状态 === "拒令" ? "坏" : "淡"}>{r.状态}</td>
                  <td><span className={"版徽 钉版徽" + (漂 ? " 旧版亮" : "")}>{r.钉住期望版 > 0 ? "v" + r.钉住期望版 : "—"}</span></td>
                  <td><span className="版徽 当前徽">v{r.当前期望版 ?? 0}</span></td>
                  <td><版源徽 版源={r.版源} 策略={r.取版策略} /></td>
                  <td>{r.执行期望版 ? "v" + r.执行期望版 : "—"}</td>
                  <td style={{ maxWidth: 260 }}><载荷摘 s={r.执行载荷} /></td>
                  <td><button className="小钮" onClick={() => 核行(r.令号)}>核验/回翻</button></td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={9} className="淡">暂无指令，先跑上方自动化场景。</td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
