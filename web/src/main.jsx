import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const apps = [
  { id: "cmdb", name: "CMDB & IS Governance", description: "Reconcile CMDB and Inventory Services data, govern catalog values, and produce controlled load candidates.", state: "ACTIVE", tone: "active" },
  { id: "gap", name: "Infrastructure Gap Analysis", description: "Correlate infrastructure-tool evidence with CMDB and recommend remediation actions.", state: "DEVELOPMENT", tone: "muted" },
  { id: "qir", name: "Quarterly Inventory Review", description: "Run governed quarterly inventory tests, evidence collection, review and sign-off.", state: "DEVELOPMENT", tone: "muted" }
];

const operations = [
  ["Network reconciliation", "Compare network CMDB records against current IS inventory.", "NW_RECONCILIATION"],
  ["Server reconciliation", "Identify server inventory gaps and required IS updates.", "SERVER_RECONCILIATION"],
  ["OS bulk governance", "Validate operating-system candidates before controlled load generation.", "OS_BULK_LOAD"],
  ["Hardware governance", "Resolve physical devices against the authoritative IS hardware catalog.", "HARDWARE_GOVERNANCE"]
];

function Icon({ name }) {
  const paths = {
    grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    home: "M3 11 12 3l9 8M5 10v10h14V10M9 20v-6h6v6",
    shield: "M12 3 20 7v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V7z",
    activity: "M3 12h4l2-7 4 14 2-7h6",
    database: "M4 6c0-2 3.6-3 8-3s8 1 8 3-3.6 3-8 3-8-1-8-3Zm0 0v6c0 2 3.6 3 8 3s8-1 8-3V6m-16 6v6c0 2 3.6 3 8 3s8-1 8-3v-6",
    layers: "m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5",
    clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
    alert: "M12 4 3 20h18zM12 9v5m0 3h.01",
    check: "m5 12 4 4L19 6",
    arrow: "M5 12h14m-6-6 6 6-6 6",
    search: "m20 20-4.5-4.5M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15",
    menu: "M4 7h16M4 12h16M4 17h16",
    settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0-5v2m0 14v2m9-9h-2M5 12H3m15.4-6.4-1.4 1.4M7 17l-1.4 1.4m12.8 0L17 17M7 7 5.6 5.6",
    plus: "M12 5v14M5 12h14"
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name] || paths.grid}/></svg>;
}

function Badge({ children, tone = "neutral" }) {
  return <span className={"badge " + tone}>{children}</span>;
}

function Stat({ label, value, delta, tone }) {
  return <div className="stat-card">
    <div className="stat-top"><span>{label}</span><Icon name={tone === "warn" ? "alert" : tone === "good" ? "check" : "activity"} /></div>
    <div className="stat-value">{value}</div>
    <div className="stat-delta">{delta}</div>
  </div>;
}

function Sidebar({ active, setActive }) {
  const nav = [
    ["overview", "Overview", "home"],
    ["governance", "Governance", "shield"],
    ["reconciliation", "Reconciliation", "layers"],
    ["jobs", "Jobs & runs", "clock"],
    ["exceptions", "Exceptions", "alert"],
    ["audit", "Audit & evidence", "database"]
  ];
  return <aside className="sidebar">
    <div className="brand">
      <div className="brand-mark"><Icon name="grid"/></div>
      <div><strong>Reconciliation</strong><span>Recommendation Platform</span></div>
    </div>
    <div className="app-selector">
      <div className="eyebrow">ACTIVE APPLICATION</div>
      <div className="app-name"><span className="status-dot"/> CMDB & IS Governance</div>
      <Badge tone="active">LOCAL EDITION</Badge>
    </div>
    <nav>
      {nav.map(([id,label,icon]) => <button key={id} className={active === id ? "nav-item selected" : "nav-item"} onClick={() => setActive(id)}>
        <Icon name={icon}/><span>{label}</span>
      </button>)}
    </nav>
    <div className="sidebar-bottom">
      <div className="environment"><span className="status-dot"/> Engine ready <small>V1.4.1</small></div>
      <button className="nav-item"><Icon name="settings"/><span>Settings</span></button>
    </div>
  </aside>;
}

function Header({ active }) {
  return <header className="header">
    <div className="mobile-menu"><Icon name="menu"/></div>
    <div className="crumb">CMDB & IS Governance <span>/</span> {active.replace("-", " ")}</div>
    <div className="header-actions">
      <div className="search"><Icon name="search"/><span>Search assets, jobs, evidence...</span><kbd>⌘ K</kbd></div>
      <div className="user"><div className="avatar">VV</div><div><strong>Governance Admin</strong><small>Local identity</small></div></div>
    </div>
  </header>;
}

function Overview({ setActive }) {
  return <div className="page">
    <div className="page-heading">
      <div><div className="eyebrow">ENTERPRISE GOVERNANCE</div><h1>Governance overview</h1><p>Monitor reconciliation health, catalog compliance and controlled inventory actions.</p></div>
      <button className="primary" onClick={() => setActive("reconciliation")}><Icon name="plus"/> New governance run</button>
    </div>
    <div className="stats">
      <Stat label="Assets evaluated" value="18,426" delta="↑ 8.4% vs previous run" tone="good"/>
      <Stat label="Reconciled" value="16,982" delta="92.2% matched to IS" tone="good"/>
      <Stat label="Review required" value="1,118" delta="6.1% needs human review" tone="warn"/>
      <Stat label="Catalog exceptions" value="326" delta="1.8% requires catalog action" tone="warn"/>
    </div>
    <div className="grid-main">
      <section className="panel">
        <div className="panel-head"><div><h2>Governance posture</h2><p>Current decision distribution across the latest completed run.</p></div><button className="ghost">View details <Icon name="arrow"/></button></div>
        <div className="posture">
          <div className="donut"><div><strong>92%</strong><span>controlled</span></div></div>
          <div className="legend">
            <div><span className="dot load"/> <strong>Load eligible</strong><b>16,982</b></div>
            <div><span className="dot review"/> <strong>Human review</strong><b>1,118</b></div>
            <div><span className="dot block"/> <strong>Blocked</strong><b>326</b></div>
          </div>
        </div>
      </section>
      <section className="panel">
        <div className="panel-head"><div><h2>Recent runs</h2><p>Execution history</p></div><button className="ghost" onClick={() => setActive("jobs")}>All runs <Icon name="arrow"/></button></div>
        <div className="run-list">
          {[
            ["NW reconciliation", "Today, 09:14", "8,240", "Completed", "good"],
            ["Server reconciliation", "Yesterday, 18:42", "9,866", "Completed", "good"],
            ["Hardware governance", "Yesterday, 15:08", "1,284", "Review", "review"]
          ].map(r => <div className="run-row" key={r[0]}><div className="run-icon"><Icon name="layers"/></div><div className="run-info"><strong>{r[0]}</strong><small>{r[1]} · {r[2]} records</small></div><Badge tone={r[4]}>{r[3]}</Badge></div>)}
        </div>
      </section>
    </div>
    <section className="panel">
      <div className="panel-head"><div><h2>Governance workspaces</h2><p>Each operation maps to a controlled business capability.</p></div></div>
      <div className="operation-grid">
        {operations.map(([title,desc,id],i) => <button className="operation" key={id} onClick={() => setActive("reconciliation")}><div className="operation-icon"><Icon name={i === 3 ? "shield" : i === 2 ? "database" : "layers"}/></div><div><strong>{title}</strong><p>{desc}</p><span>Open workspace <Icon name="arrow"/></span></div></button>)}
      </div>
    </section>
  </div>;
}

function Reconciliation({ setActive }) {
  const [selected, setSelected] = useState("Network reconciliation");
  return <div className="page">
    <div className="page-heading"><div><div className="eyebrow">CONTROLLED EXECUTION</div><h1>Reconciliation workspace</h1><p>Run deterministic governance operations while preserving evidence and review boundaries.</p></div><Badge tone="active">ENGINE READY</Badge></div>
    <div className="workspace">
      <div className="workspace-nav">{operations.map(([title,desc]) => <button key={title} className={selected === title ? "workspace-link selected" : "workspace-link"} onClick={() => setSelected(title)}><strong>{title}</strong><small>{desc}</small></button>)}</div>
      <div className="workspace-body">
        <div className="callout"><div className="callout-icon"><Icon name="shield"/></div><div><strong>Governance-first execution</strong><p>Catalog-controlled values are resolved before a load candidate can be produced. Similarity alone never authorizes an IS load.</p></div></div>
        <div className="form-grid">
          <label>CMDB source<input placeholder="Select CMDB report" value="NW CMDB Report" readOnly/></label>
          <label>IS inventory<input placeholder="Select IS report" value="IS Network Category Report" readOnly/></label>
          <label>Catalog<input value="IS Product Catalog Network" readOnly/></label>
          <label>Execution mode<select defaultValue="analysis"><option value="analysis">Analysis + recommendations</option><option value="load">Generate controlled load candidates</option></select></label>
        </div>
        <div className="run-config"><div><strong>{selected}</strong><p>Inputs are processed locally. No external service is required for the core engine.</p></div><button className="primary" onClick={() => setActive("jobs")}><Icon name="activity"/> Start analysis</button></div>
      </div>
    </div>
  </div>;
}

function Governance() {
  const rows = [
    ["Cisco IOS XE 17.12.07", "Cisco IOS-XE 17.12.7", "Normalized", "LOAD"],
    ["Windows 2022 Server", "Microsoft Windows Server 2022 Standard", "Catalog match", "LOAD"],
    ["Juniper EX Series", "—", "Ambiguous", "REVIEW"],
    ["Ubuntu 24.04 LTS", "—", "No catalog match", "CATALOG"]
  ];
  return <div className="page"><div className="page-heading"><div><div className="eyebrow">AUTHORITATIVE CATALOG</div><h1>Governance decisions</h1><p>Every governed value retains source evidence, resolution method and authorization status.</p></div><button className="ghost"><Icon name="database"/> Export evidence</button></div>
    <section className="panel table-panel"><div className="toolbar"><div className="tabs"><button className="tab active">All decisions</button><button className="tab">Load</button><button className="tab">Review</button><button className="tab">Catalog action</button></div><div className="search small"><Icon name="search"/><span>Filter decisions...</span></div></div>
      <table><thead><tr><th>Source value</th><th>Resolved IS value</th><th>Resolution</th><th>Decision</th><th></th></tr></thead><tbody>{rows.map((r,i)=><tr key={i}><td><strong>{r[0]}</strong><small>CMDB evidence</small></td><td>{r[1]}</td><td><Badge tone={r[2] === "Ambiguous" ? "review" : r[2] === "No catalog match" ? "block" : "good"}>{r[2]}</Badge></td><td><Badge tone={r[3] === "LOAD" ? "good" : r[3] === "REVIEW" ? "review" : "block"}>{r[3]}</Badge></td><td>⋯</td></tr>)}</tbody></table>
    </section>
  </div>;
}

function GenericPage({ type }) {
  const content = {
    jobs: ["Jobs & runs", "Track execution state, metrics and output artifacts.", "12 runs", "8 completed · 3 review · 1 blocked"],
    exceptions: ["Exceptions", "Review governed records that require human intervention.", "326 open", "Ambiguous catalog matches and data-quality exceptions"],
    audit: ["Audit & evidence", "Trace every recommendation from source evidence to governed action.", "18,426 decisions", "Evidence retention is local in this edition"]
  }[type];
  return <div className="page"><div className="page-heading"><div><div className="eyebrow">PLATFORM OPERATIONS</div><h1>{content[0]}</h1><p>{content[1]}</p></div><Badge tone="active">LOCAL MODE</Badge></div><div className="empty-enterprise"><div className="empty-icon"><Icon name={type === "audit" ? "database" : type === "jobs" ? "clock" : "alert"}/></div><h2>{content[2]}</h2><p>{content[3]}</p><button className="primary">Open workspace <Icon name="arrow"/></button></div></div>;
}

function App() {
  const [active, setActive] = useState("overview");
  const page = active === "overview" ? <Overview setActive={setActive}/> : active === "governance" ? <Governance/> : active === "reconciliation" ? <Reconciliation setActive={setActive}/> : <GenericPage type={active}/>;
  return <div className="app"><Sidebar active={active} setActive={setActive}/><main><Header active={active}/>{page}</main></div>;
}

createRoot(document.getElementById("root")).render(<App />);
