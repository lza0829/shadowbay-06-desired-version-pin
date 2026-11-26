import React, { useEffect, useState } from "react";
import { get, post } from "../api.js";

function 美化(j) {
  try {
    return JSON.stringify(typeof j === "string" ? JSON.parse(j) : j, null, 2);
  } catch {
    return String(j || "{}");
  }
}

export default function 入口() {
  const [d, setD] = useState(null);
  const [影, set影] = useState(null);
  const [msg, setMsg] = useState("");
  const 刷 = async () => {
    const [o, s] = await Promise.all([get("/总览"), get("/影子台")]);
    setD(o);
    set影(s[0] || null);
  };
  useEffect(() => {
    刷().catch((e) => setMsg(String(e)));
  }, []);

  return (
    <div>
      <h2 className="题">对影入口</h2>
      <p className="述">不是设备资产台，不是充桩计量。左边期望、右边上报；中间灯亮表示可对齐。</p>
      <div className="行">
        <button
          className="主钮"
          onClick={() =>
            post("/演示/对影闭环")
              .then(() => {
                setMsg("对影闭环已演练：对齐 → 送达 → 补投 → 旧证拒令");
                return 刷();
              })
              .catch((e) => setMsg(String(e)))
          }
        >
          演练对影闭环
        </button>
        <button className="铜钮" onClick={() => 刷().catch((e) => setMsg(String(e)))}>
          刷新
        </button>
        {msg && <span className="讯">{msg}</span>}
      </div>

      <div className="对影">
        <section className="影栏">
          <div className="影眉">Desired · 期望</div>
          <div className="影体">{影 ? 美化(影.期望载荷) : "尚无设备影子"}</div>
        </section>
        <div className="影缝">
          <div className="点" />
          {影 ? 影.对齐态 : "待命"}
        </div>
        <section className="影栏 上报">
          <div className="影眉">Reported · 上报</div>
          <div className="影体">{影 ? 美化(影.上报载荷) : "等待端侧回声"}</div>
        </section>
      </div>

      {d && (
        <div className="带条">
          {Object.entries(d).map(([k, v]) => (
            <div className="带项" key={k}>
              <b>{v}</b>
              <span>{k}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
