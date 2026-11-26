import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";

export default function 影子台() {
  const [rows, setRows] = useState([]);
  const 刷 = () => get("/影子台").then(setRows);
  useEffect(() => {
    刷();
  }, []);
  return (
    <div>
      <h2 className="题">影子台</h2>
      <p className="述">期望与上报 JSON 全等才算已齐；上报会把设备标为在线。</p>
      <div className="行">
        <button className="主钮" onClick={() => post("/演示/期望").then(刷)}>
          写入期望
        </button>
        <button className="铜钮" onClick={() => post("/演示/上报").then(刷)}>
          回声上报
        </button>
        <button onClick={刷}>刷新</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>设备</th>
            <th>对齐</th>
            <th>期望版</th>
            <th>上报版</th>
            <th>期望</th>
            <th>上报</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.设备键}>
              <td>
                {r.别名 || r.设备键}
                <div className="淡">{r.设备键}</div>
              </td>
              <td className={r.对齐态 === "已齐" ? "好" : "坏"}>{r.对齐态}</td>
              <td>{r.期望版}</td>
              <td>{r.上报版}</td>
              <td className="淡">{r.期望载荷}</td>
              <td className="淡">{r.上报载荷}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
