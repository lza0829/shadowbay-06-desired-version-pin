import React, { useState } from "react";
import { get } from "./api.js";

function JSON块({ value }) {
  if (value === null || value === undefined || value === "")
    return <span className="淡">—（无）</span>;
  let txt;
  try {
    txt = typeof value === "string" ? JSON.stringify(JSON.parse(value), null, 2) : JSON.stringify(value, null, 2);
  } catch {
    txt = String(value);
  }
  return <pre className="JSON块">{txt}</pre>;
}

export function 版源徽({ 版源, 策略 }) {
  const 钉 = 版源 === "下发时钉版" || 策略 === "钉版";
  const 读 = 版源 === "执行时读最新" || 策略 === "读最新";
  return (
    <span className={"徽 " + (钉 ? "徽铜" : 读 ? "徽钢" : "徽淡")}>
      {版源 || (策略 === "读最新" ? "执行时读最新" : 策略 === "钉版" ? "下发时钉版" : "—")}
    </span>
  );
}

/** 核验结果卡：规格要求的 令号 / 钉住的期望版 / 当前期望版 / 执行载荷 / valid 同卡给出。 */
export function 核验卡({ v, onClose }) {
  if (!v) return null;
  const valid = v.valid === true;
  return (
    <div className={"核验卡 " + (valid ? "核验好" : "核验坏")}>
      <div className="核验头">
        <b>令号回翻核验</b>
        <span className={"徽 " + (valid ? "徽磷" : "徽红")}>valid: {String(v.valid)}</span>
        {onClose && (
          <button className="小钮" onClick={onClose} style={{ marginLeft: "auto" }}>
            关闭
          </button>
        )}
      </div>
      <div className="核验格">
        <div><span>令号</span><code>{v.令号}</code></div>
        <div><span>钉住的期望版</span><b className="铜字">{v["钉住的期望版"] ?? "未钉（读最新）"}</b></div>
        <div><span>当前期望版</span><b className="磷字">{v["当前期望版"]}</b></div>
        <div><span>执行期望版</span><b>{v.执行期望版 ?? "—"}</b></div>
        <div><span>版源</span><版源徽 版源={v.版源} 策略={v.取版策略} /></div>
        <div><span>令源/路径</span><b>{v.令源 || "—"}</b></div>
        <div><span>版漂</span><b className={v.版漂 ? "铜字" : "淡"}>{v.版漂 ? "是 · 钉旧版/当前新版" : "否"}</b></div>
        <div><span>版本史同票</span><b className={v.同票 ? "好" : "淡"}>{String(!!v.同票)}</b></div>
      </div>
      <div className="核验载">
        <div className="淡">执行载荷（版源所指）</div>
        <JSON块 value={v.执行载荷} />
      </div>
      <details className="核验载">
        <summary className="淡" style={{ cursor: "pointer" }}>钉住的期望快照</summary>
        <JSON块 value={v.期望快照} />
      </details>
      {v.核验说明 && <p className={"讯 " + (valid ? "好" : "坏")} style={{ marginBottom: 0 }}>{v.核验说明}</p>}
    </div>
  );
}

/** 按令号回翻：影子台 / 指令廊 / 版本钉页共用。 */
export function 令号回翻({ 初始 = "", 自动核验 = false }) {
  const [号, set号] = useState(初始);
  const [v, setV] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function 核(target) {
    const q = (target ?? 号).trim();
    if (!q) return;
    setLoading(true);
    setErr("");
    try {
      const j = await get("/期望版本钉/核验?令号=" + encodeURIComponent(q));
      setV(j);
    } catch (e) {
      setV(null);
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  // 外部带入初始令号时自动核一次
  React.useEffect(() => {
    if (自动核验 && 初始) 核(初始);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [初始]);

  return (
    <div className="回翻">
      <div className="行" style={{ marginBottom: v ? "0.7rem" : 0 }}>
        <input
          className="令号输入"
          placeholder="输入令号 CMD-… 按令号回翻"
          value={号}
          onChange={(e) => set号(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && 核()}
        />
        <button className="主钮" onClick={() => 核()} disabled={loading}>
          {loading ? "核验中…" : "按令号核验"}
        </button>
      </div>
      {err && <p className="坏 讯">{err}</p>}
      {v && <核验卡 v={v} onClose={() => setV(null)} />}
    </div>
  );
}

/** 断言清单渲染（场景自动化端点返回的 断言[]）。 */
export function 断言清单({ list }) {
  if (!list?.length) return null;
  const 全过 = list.every((a) => a.通过);
  return (
    <div className="断言列">
      <div className={"断言总 " + (全过 ? "徽磷" : "徽红")}>
        {全过 ? "✅ 全部断言通过" : "❌ 存在失败断言"}（{list.filter((a) => a.通过).length}/{list.length}）
      </div>
      {list.map((a, i) => (
        <div key={i} className={"断言行 " + (a.通过 ? "过" : "败")}>
          <span>{a.通过 ? "✓" : "✗"}</span>
          <span className="断言名">{a.名}</span>
          {!a.通过 && <code className="断言实">实际 {JSON.stringify(a.实际)} ／ 期望 {JSON.stringify(a.期望)}</code>}
        </div>
      ))}
    </div>
  );
}
