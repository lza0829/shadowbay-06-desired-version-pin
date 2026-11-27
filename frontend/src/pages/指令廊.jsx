import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";
import { 核验卡, 令号回翻, 版源徽 } from "../钉版件.jsx";

export default function 指令廊() {
  const [rows, setRows] = useState([]);
  const [last, setLast] = useState(null);
  const [focus, setFocus] = useState(null);
  const [msg, setMsg] = useState("");
  // 令册 LEFT JOIN 影子台，自带“当前期望版”，与钉住列同屏。
  const 刷 = () => get("/期望版本钉/令册").then(setRows).catch((e) => setMsg(String(e.message || e)));
  useEffect(() => {
    刷();
  }, []);

  async function 核(号) {
    try {
      setFocus(await get("/期望版本钉/核验?令号=" + encodeURIComponent(号)));
    } catch (e) {
      setMsg(String(e.message || e));
    }
  }

  return (
    <div>
      <h2 className="题">指令廊</h2>
      <p className="述">
        在线直达为送达；离线入在途并进补投条；指纹不符即拒令。每条令都留下
        <b className="铜字"> 钉住期望版 + 期望快照 + 版源</b>
        （读最新对照除外，其在途只存动作），钉住版与设备当前期望版同屏对照，可按令号回翻核验。
      </p>
      <div className="行">
        <button
          className="主钮"
          onClick={() =>
            post("/演示/下发")
              .then((x) => {
                setLast(x);
                刷();
              })
              .catch((e) => setMsg(String(e)))
          }
        >
          推演示令
        </button>
        <button onClick={刷}>刷新</button>
        {last && (
          <span className="讯">
            最近 {last.令号} · {last.状态} · 钉住 v{last.钉住期望版 ?? 0} · {last.版源 || "—"}
          </span>
        )}
        {msg && <span className="坏 讯">{msg}</span>}
      </div>

      <令号回翻 />
      {focus && <核验卡 v={focus} onClose={() => setFocus(null)} />}

      <table>
        <thead>
          <tr>
            <th>令号</th>
            <th>设备</th>
            <th>动作</th>
            <th>状态</th>
            <th>钉住期望版</th>
            <th>当前期望版</th>
            <th>版源</th>
            <th>路径</th>
            <th>指纹</th>
            <th>说明</th>
            <th>回翻</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const 漂 = r.钉住期望版 > 0 && r.当前期望版 != null && r.钉住期望版 !== r.当前期望版;
            return (
              <tr key={r.令号} className={漂 ? "行漂" : ""}>
                <td><code>{r.令号}</code></td>
                <td>{r.设备键}</td>
                <td>{r.动作}</td>
                <td className={r.状态 === "拒令" ? "坏" : r.状态 === "送达" ? "好" : "淡"}>{r.状态}</td>
                <td>
                  <span className={"版徽 钉版徽" + (漂 ? " 旧版亮" : "")}>
                    {r.钉住期望版 > 0 ? "v" + r.钉住期望版 : "未钉"}
                  </span>
                </td>
                <td><span className="版徽 当前徽">v{r.当前期望版 ?? 0}</span></td>
                <td><版源徽 版源={r.版源} 策略={r.取版策略} /></td>
                <td className="淡">{r.令源 || "—"}</td>
                <td className="淡">{r.凭证指纹}</td>
                <td className="淡">{r.说明}{漂 ? "（版漂）" : ""}</td>
                <td><button className="小钮" onClick={() => 核(r.令号)}>核验</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
