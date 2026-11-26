import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";

export default function 设备册() {
  const [rows, setRows] = useState([]);
  const 刷 = () => get("/设备册").then(setRows);
  useEffect(() => {
    刷();
  }, []);
  return (
    <div>
      <h2 className="题">设备册</h2>
      <p className="述">入册后才有影子台与指令廊；在线态决定直达或积压。</p>
      <div className="行">
        <button className="主钮" onClick={() => post("/演示/入册").then(刷)}>
          登记演示设备
        </button>
        <button onClick={刷}>刷新</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>设备键</th>
            <th>别名</th>
            <th>在线</th>
            <th>凭证指纹</th>
            <th>更新时</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.设备键}>
              <td>{r.设备键}</td>
              <td>{r.别名}</td>
              <td className={r.在线 === "在线" ? "好" : "淡"}>{r.在线}</td>
              <td className="淡">{r.凭证指纹}</td>
              <td className="淡">{r.更新时}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
