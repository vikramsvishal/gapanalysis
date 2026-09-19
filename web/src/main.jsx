import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const fallbackOperations = [
  { id:"NW_RECONCILIATION", name:"Network Reconciliation", description:"Compare network CMDB records against current IS inventory." },
  { id:"SERVER_RECONCILIATION", name:"Server Reconciliation", description:"Identify server inventory gaps and required IS updates." },
  { id:"HARDWARE_GOVERNANCE", name:"Hardware Governance", description:"Resolve physical devices against the authoritative IS hardware catalog." },
  { id:"OS_BULK_LOAD", name:"OS Bulk Governance", description:"Validate operating-system candidates before controlled load generation." }
];

function Icon({name}) {
  const p={grid:"M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",home:"M3 11 12 3l9 8M5 10v10h14V10M9 20v-6h6v6",shield:"M12 3 20 7v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V7z",activity:"M3 12h4l2-7 4 14 2-7h6",database:"M4 6c0-2 3.6-3 8-3s8 1 8 3-3.6 3-8 3-8-1-8-3Zm0 0v6c0 2 3.6 3 8 3s8-1 8-3V6",layers:"m12 3 9 5-9 5-9-5zM3 12l9 5 9-5M3 16l9 5 9-5",clock:"M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",alert:"M12 4 3 20h18zM12 9v5m0 3h.01",check:"m5 12 4 4L19 6",arrow:"M5 12h14m-6-6 6 6-6 6",search:"m20 20-4.5-4.5M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15",settings:"M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm0-5v2m0 14v2m9-9h-2M5 12H3",plus:"M12 5v14M5 12h14"};
  return <svg viewBox="0 0 24 24"><path d={p[name]||p.grid}/></svg>;
}
const Badge=({children,tone="neutral"})=><span className={"badge "+tone}>{children}</span>;

async function getJSON(path){
  const r=await fetch(path);
  if(!r.ok) throw new Error(path+" "+r.status);
  return r.json();
}

function Sidebar({active,setActive,health}){
 const nav=[["overview","Overview","home"],["governance","Governance","shield"],["reconciliation","Reconciliation","layers"],["jobs","Jobs & runs","clock"],["exceptions","Exceptions","alert"],["audit","Audit & evidence","database"]];
 return <aside className="sidebar">
  <div className="brand"><div className="brand-mark"><Icon name="grid"/></div><div><strong>Reconciliation</strong><span>Recommendation Platform</span></div></div>
  <div className="app-selector"><div className="eyebrow">ACTIVE APPLICATION</div><div className="app-name"><span className="status-dot"/> CMDB & IS Governance</div><Badge tone="active">LOCAL EDITION</Badge></div>
  <nav>{nav.map(([id,label,icon])=><button key={id} className={active===id?"nav-item selected":"nav-item"} onClick={()=>setActive(id)}><Icon name={icon}/><span>{label}</span></button>)}</nav>
  <div className="sidebar-bottom"><div className="environment"><span className={"status-dot"}/> Engine {health?.status==="READY"?"ready":"offline"} <small>V{health?.golden_version||"1.4.1"}</small></div><button className="nav-item"><Icon name="settings"/><span>Settings</span></button></div>
 </aside>;
}

function Header({active,health}){
 return <header className="header"><div className="crumb">CMDB & IS Governance <span>/</span> {active.replaceAll("-"," ")}</div><div className="header-actions"><div className="search"><Icon name="search"/><span>Search assets, jobs, evidence...</span><kbd>⌘ K</kbd></div><div className="user"><div className="avatar">VV</div><div><strong>Governance Admin</strong><small>Local identity · {health?.version||"connecting"}</small></div></div></div></header>;
}

function Overview({setActive,operations,health}){
 return <div className="page">
  <div className="page-heading"><div><div className="eyebrow">ENTERPRISE GOVERNANCE</div><h1>Governance overview</h1><p>Monitor reconciliation health, catalog compliance and controlled inventory actions.</p></div><button className="primary" onClick={()=>setActive("reconciliation")}><Icon name="plus"/> New governance run</button></div>
  <div className="stats"><div className="stat-card"><div className="stat-top"><span>Engine status</span><Icon name="check"/></div><div className="stat-value">{health?.status||"CONNECTING"}</div><div className="stat-delta">Business engine V{health?.golden_version||"1.4.1"}</div></div><div className="stat-card"><div className="stat-top"><span>Application</span><Icon name="shield"/></div><div className="stat-value">ACTIVE</div><div className="stat-delta">CMDB & IS Governance</div></div><div className="stat-card"><div className="stat-top"><span>Operations</span><Icon name="activity"/></div><div className="stat-value">{operations.length}</div><div className="stat-delta">Governance capabilities exposed</div></div><div className="stat-card"><div className="stat-top"><span>Execution mode</span><Icon name="database"/></div><div className="stat-value">LOCAL</div><div className="stat-delta">Offline-capable core processing</div></div></div>
  <div className="grid-main"><section className="panel"><div className="panel-head"><div><h2>Platform posture</h2><p>Live state from the FastAPI application boundary.</p></div><Badge tone={health?.status==="READY"?"good":"review"}>{health?.status||"CONNECTING"}</Badge></div><div className="posture"><div className="donut"><div><strong>{health?.golden_version||"1.4.1"}</strong><span>golden engine</span></div></div><div className="legend"><div><span className="dot load"/><strong>Application</strong><b>V{health?.version||"—"}</b></div><div><span className="dot review"/><strong>Mode</strong><b>{health?.mode||"—"}</b></div><div><span className="dot block"/><strong>Transport</strong><b>FastAPI</b></div></div></div></section>
  <section className="panel"><div className="panel-head"><div><h2>Architecture boundary</h2><p>UI never imports the business engine directly.</p></div></div><div className="run-list"><div className="run-row"><div className="run-icon"><Icon name="layers"/></div><div className="run-info"><strong>React / Vite</strong><small>Enterprise presentation layer</small></div><Badge tone="good">READY</Badge></div><div className="run-row"><div className="run-icon"><Icon name="activity"/></div><div className="run-info"><strong>FastAPI</strong><small>Application transport boundary</small></div><Badge tone="good">READY</Badge></div><div className="run-row"><div className="run-icon"><Icon name="shield"/></div><div className="run-info"><strong>V1.4.1 Golden Engine</strong><small>Business behavior preserved</small></div><Badge tone="good">PROTECTED</Badge></div></div></section></div>
  <section className="panel"><div className="panel-head"><div><h2>Governance workspaces</h2><p>Capabilities are sourced from the API rather than duplicated in the UI.</p></div></div><div className="operation-grid">{operations.map((o,i)=><button className="operation" key={o.id} onClick={()=>setActive("reconciliation")}><div className="operation-icon"><Icon name={i===3?"shield":i===2?"database":"layers"}/></div><div><strong>{o.name}</strong><p>{o.description}</p><span>Open workspace <Icon name="arrow"/></span></div></button>)}</div></section>
 </div>;
}

function Reconciliation({operations}){
 const [selected,setSelected]=useState(operations[0]?.id||"NW_RECONCILIATION");
 const op=operations.find(x=>x.id===selected)||operations[0];
 return <div className="page"><div className="page-heading"><div><div className="eyebrow">CONTROLLED EXECUTION</div><h1>Reconciliation workspace</h1><p>Run deterministic governance operations while preserving evidence and review boundaries.</p></div><Badge tone="active">ENGINE READY</Badge></div><div className="workspace"><div className="workspace-nav">{operations.map(o=><button key={o.id} className={selected===o.id?"workspace-link selected":"workspace-link"} onClick={()=>setSelected(o.id)}><strong>{o.name}</strong><small>{o.description}</small></button>)}</div><div className="workspace-body"><div className="callout"><div className="callout-icon"><Icon name="shield"/></div><div><strong>Governance-first execution</strong><p>Catalog-controlled values must resolve against the authoritative catalog before a load candidate is produced. Similarity alone never authorizes an IS load.</p></div></div><div className="form-grid"><label>Operation<input value={op?.name||""} readOnly/></label><label>Execution mode<select defaultValue="analysis"><option>Analysis + recommendations</option><option>Generate controlled load candidates</option></select></label><label>Input handling<input value="Local files / configured resources" readOnly/></label><label>Evidence<input value="Preserved with governance decision" readOnly/></label></div><div className="run-config"><div><strong>{op?.name}</strong><p>{op?.capability||"Governance operation"} is exposed through the application service.</p></div><button className="primary" onClick={()=>alert("Execution endpoint will be enabled with the job service in the next slice.")}><Icon name="activity"/> Start analysis</button></div></div></div></div>;
}

function Generic({type}){const c={jobs:["Jobs & runs","Execution state, metrics and output artifacts."],exceptions:["Exceptions","Records requiring human intervention."],audit:["Audit & evidence","Trace recommendations from evidence to governed action."]}[type];return <div className="page"><div className="page-heading"><div><div className="eyebrow">PLATFORM OPERATIONS</div><h1>{c[0]}</h1><p>{c[1]}</p></div><Badge tone="active">LOCAL MODE</Badge></div><div className="empty-enterprise"><div className="empty-icon"><Icon name={type==="audit"?"database":type==="jobs"?"clock":"alert"}/></div><h2>API-ready workspace</h2><p>This surface is intentionally dormant until its domain service is implemented.</p></div></div>}

function App(){
 const [active,setActive]=useState("overview"),[health,setHealth]=useState(null),[operations,setOperations]=useState(fallbackOperations),[error,setError]=useState("");
 useEffect(()=>{Promise.all([getJSON("/api/health"),getJSON("/api/governance/operations")]).then(([h,o])=>{setHealth(h);setOperations(o.items||fallbackOperations)}).catch(e=>setError(e.message))},[]);
 const page=active==="overview"?<Overview setActive={setActive} operations={operations} health={health}/>:active==="reconciliation"?<Reconciliation operations={operations}/>:active==="governance"?<Generic type="audit"/>:<Generic type={active}/>;
 return <div className="app"><Sidebar active={active} setActive={setActive} health={health}/><main><Header active={active} health={health}/>{error&&<div style={{margin:"12px 32px",padding:"10px",background:"#fff1f2",border:"1px solid #fecdd3",borderRadius:8,fontSize:11}}>API connection: {error}</div>}{page}</main></div>;
}
createRoot(document.getElementById("root")).render(<App />);
