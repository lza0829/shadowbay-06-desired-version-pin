import React, { useEffect, useState } from "react";
import { get } from "../api.js";

export default function 对影验() {
  const [rows, setRows] = useState([]);
  const 刷 = () => get("/对影验").then(setRows);
  useEffect(() => {
    刷();
  }, []);
  return (
    <div>
      <h2 className="题">对影验</h2>
      <p className="述">影子已齐、无在途/积压、凭证与最近轮一致 → 通过。</p>
      <div className="行">
        <button className="主钮" onClick={刷}>
          重验
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th>设备</th>
            <th>结果</th>
            <th>对齐</th>
            <th>在线</th>
            <th>指纹</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.设备键}>
              <td>
                {r.别名}
                <div className="淡">{r.设备键}</div>
              </td>
              <td className={r.通过 ? "好" : "坏"}>{r.通过 ? "通过" : "未过"}</td>
              <td>{r.对齐态}</td>
              <td>{r.在线}</td>
              <td className="淡">{r.凭证指纹}</td>
              <td className="淡">{r.说明}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
