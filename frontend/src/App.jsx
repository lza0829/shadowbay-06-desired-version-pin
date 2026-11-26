import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import 入口 from "./pages/入口.jsx";
import 设备册 from "./pages/设备册.jsx";
import 影子台 from "./pages/影子台.jsx";
import 指令廊 from "./pages/指令廊.jsx";
import 断线补投 from "./pages/断线补投.jsx";
import 凭证轮 from "./pages/凭证轮.jsx";
import 对影验 from "./pages/对影验.jsx";

const 链 = [
  ["/", "入口"],
  ["/设备册", "设备册"],
  ["/影子台", "影子台"],
  ["/指令廊", "指令廊"],
  ["/断线补投", "断线补投"],
  ["/凭证轮", "凭证轮"],
  ["/对影验", "对影验"],
];

export default function App() {
  return (
    <div className="壳">
      <header className="顶轨">
        <div className="顶牌">
          <div>
            <div className="顶英">Shadowbay · IoT</div>
            <h1 className="顶名">影<span>湾</span></h1>
          </div>
          <p className="顶骨">设备入册后对齐期望与上报影子；下行指令走在途与补投，凭证轮换后旧指纹拒令。</p>
        </div>
        <nav className="顶导">
          {链.map(([to, l]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "亮" : "")}>
              {l}
            </NavLink>
          ))}
          <span className="顶脚标" style={{ marginLeft: "auto", alignSelf: "center" }}>
            SYS · IoT · :7100
          </span>
        </nav>
      </header>
      <main className="主">
        <Routes>
          <Route path="/" element={<入口 />} />
          <Route path="/设备册" element={<设备册 />} />
          <Route path="/影子台" element={<影子台 />} />
          <Route path="/指令廊" element={<指令廊 />} />
          <Route path="/断线补投" element={<断线补投 />} />
          <Route path="/凭证轮" element={<凭证轮 />} />
          <Route path="/对影验" element={<对影验 />} />
        </Routes>
      </main>
    </div>
  );
}
