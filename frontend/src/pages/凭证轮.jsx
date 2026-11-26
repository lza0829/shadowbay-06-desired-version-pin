import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";

export default function 凭证轮() {
  const [rows, setRows] = useState([]);
  const [msg, setMsg] = useState("");
  const 刷 = () => get("/凭证轮").then(setRows);
  useEffect(() => {
    刷();
  }, []);
  return (
    <div>
      <h2 className="题">凭证轮</h2>
      <p className="述">轮换后在册指纹切换；再用旧指纹下发会被拒令。不是站点 TLS 证更。</p>
      <div className="行">
        <button
          className="主钮"
          onClick={() =>
            post("/凭证轮/轮换", { 设备键: "dev-bay-01", 新指纹: "fp-rotated-01" })
              .then((x) => {
                setMsg(`轮号 ${x.轮号}`);
                刷();
              })
              .catch((e) => setMsg(String(e)))
          }
        >
          轮换到 fp-rotated-01
        </button>
        <button onClick={刷}>刷新</button>
        {msg && <span className="讯">{msg}</span>}
      </div>
      <table>
        <thead>
          <tr>
            <th>轮号</th>
            <th>设备</th>
            <th>旧指纹</th>
            <th>新指纹</th>
            <th>生效时</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.轮号}>
              <td>{r.轮号}</td>
              <td>{r.设备键}</td>
              <td className="淡">{r.旧指纹}</td>
              <td className="好">{r.新指纹}</td>
              <td className="淡">{r.生效时}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
