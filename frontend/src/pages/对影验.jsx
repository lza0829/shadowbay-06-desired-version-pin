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
      <p className="述">
        影子以<b>当前期望版</b>为准判齐，不拿令廊钉住的旧快照比对，故不会因版漂误判“已齐”；
        单纯“令钉旧版、期望已新版”只计版漂、不判失败误报。只有缺钉版/快照、篡改或执行漂版，
        才计为钉版异常并判未过。
      </p>
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
            <th>当前期望版</th>
            <th>上报版</th>
            <th>版漂令数（不判失败）</th>
            <th>钉版异常</th>
            <th>在线</th>
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
              <td><span className="版徽 当前徽">v{r.当前期望版 ?? 0}</span></td>
              <td>v{r.上报版 ?? 0}</td>
              <td className={r.版漂令数 ? "铜字" : "淡"}>{r.版漂令数 ?? 0}</td>
              <td className={r.钉版异常令数 ? "坏" : "好"}>
                {r.钉版异常令数 ?? 0}
                {r.钉版异常?.length > 0 && (
                  <div className="淡">
                    {r.钉版异常.map((x) => (
                      <div key={x.令号}><code>{x.令号}</code> {x.问题}</div>
                    ))}
                  </div>
                )}
              </td>
              <td>{r.在线}</td>
              <td className="淡">{r.说明}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
