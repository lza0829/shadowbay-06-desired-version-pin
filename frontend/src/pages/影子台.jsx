import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";
import { 令号回翻 } from "../钉版件.jsx";

export default function 影子台() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const 刷 = () => get("/影子台").then(setRows).catch((e) => setMsg(String(e.message || e)));
  useEffect(() => {
    刷();
  }, []);
  return (
    <div>
      <h2 className="题">影子台</h2>
      <p className="述">
        期望与上报 JSON 全等才算已齐；上报会把设备标为在线。每台设备被令廊
        <b className="铜字"> 钉住的期望版</b> 以铜徽高亮；当前期望版若正被钉住会加亮框。
        版漂（令钉 v1、影子已 v2）在此可见，但不改变“以当前期望判齐”。
      </p>
      <div className="行">
        <button className="主钮" onClick={() => post("/演示/期望").then(刷)}>
          写入期望
        </button>
        <button className="铜钮" onClick={() => post("/演示/上报").then(刷)}>
          回声上报
        </button>
        <button onClick={刷}>刷新</button>
        {msg && <span className="坏 讯">{msg}</span>}
      </div>

      <令号回翻 />

      <table>
        <thead>
          <tr>
            <th>设备</th>
            <th>对齐</th>
            <th>当前期望版</th>
            <th>上报版</th>
            <th>钉住版（高亮）</th>
            <th>期望</th>
            <th>上报</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const 钉列 = r.钉住版本 || [];
            const 当前被钉 = 钉列.includes(r.期望版);
            return (
              <tr key={r.设备键}>
                <td>
                  {r.别名 || r.设备键}
                  <div className="淡">{r.设备键}</div>
                </td>
                <td className={r.对齐态 === "已齐" ? "好" : "坏"}>{r.对齐态}</td>
                <td>
                  <span className={"版徽 当前徽" + (当前被钉 ? " 当前被钉" : "")}>v{r.期望版}</span>
                </td>
                <td>{r.上报版}</td>
                <td>
                  <div className="钉版堆">
                    {钉列.length === 0 && <span className="淡">—</span>}
                    {钉列.map((v) => (
                      <span key={v} className="版徽 钉版徽 旧版亮" title={r.钉住版本计数?.[v] ? `${r.钉住版本计数[v]} 条令钉此版` : ""}>
                        钉 v{v}{r.钉住版本计数?.[v] ? ` ×${r.钉住版本计数[v]}` : ""}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="淡"><pre className="单元格JSON">{r.期望载荷}</pre></td>
                <td className="淡"><pre className="单元格JSON">{r.上报载荷}</pre></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
