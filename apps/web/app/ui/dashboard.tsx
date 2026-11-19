"use client";

import { useState } from "react";

type Data = { cells: any[]; alerts: any[]; reports: any[] };
export default function Dashboard({ initial }: { initial: Data }) {
  const [data, setData] = useState(initial);
  const [message, setMessage] = useState("");
  async function action(path: string, method = "POST", body?: unknown) {
    const response = await fetch(`/api/action?path=${encodeURIComponent(path)}`, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) { setMessage("Action failed. Refresh and try again."); return null; }
    return response.json();
  }
  async function review(id: string, decision: "accepted" | "rejected") {
    await action(`/reports/${id}/review`, "POST", { decision }); setData({ ...data, reports: data.reports.filter((r) => r.id !== id) }); setMessage(`Report ${decision}.`);
  }
  async function approve(id: string, accepted: boolean) {
    await action(`/alerts/${id}/${accepted ? "approve" : "reject"}`, "POST", accepted ? undefined : { reason: "Officer review" });
    setData({ ...data, alerts: data.alerts.map((a) => a.id === id ? { ...a, status: accepted ? "approved" : "rejected" } : a) });
    setMessage(accepted ? "Alert approved; dispatch workflow resumed." : "Alert rejected.");
  }
  async function startRun(cellId: string) {
    const run = await action(`/cells/${encodeURIComponent(cellId)}/agent-run`);
    if (!run) return;
    const alerts = await action("/alerts", "GET");
    if (alerts) setData({ ...data, alerts });
    setMessage(run.alert_id ? "Alert draft created. Officer approval is required." : `Run status: ${run.status}.`);
  }
  async function logout() { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; }
  const hot = data.cells.filter((x) => x.properties?.risk_p != null).sort((a, b) => b.properties.risk_p - a.properties.risk_p).slice(0, 8);
  return <main className="appShell"><header className="topbar"><div className="brand"><span className="brandMark">L</span><span>Liveslide <small>OFFICER DESK</small></span></div><div className="topActions"><span className="live"><i /> DEMO GRID</span><button className="quiet" onClick={logout}>Sign out</button></div></header>
    <section className="pageHead"><div><div className="eyebrow">ASSAM · MONITORING</div><h1>Risk overview</h1><p>Review local signals and community reports before taking action.</p></div><span className="date">Operational view · Latest available scores</span></section>
    {message && <div className="notice">{message}<button onClick={() => setMessage("")}>×</button></div>}
    <section className="stats"><article><span>Mapped cells</span><strong>{data.cells.length}</strong><small>in current view</small></article><article><span>High risk cells</span><strong>{data.cells.filter((c) => c.properties?.risk_p >= .8).length}</strong><small>risk score ≥ 0.80</small></article><article><span>Reports to review</span><strong>{data.reports.length}</strong><small>community submissions</small></article><article><span>Alert drafts</span><strong>{data.alerts.filter((a) => a.status === "draft").length}</strong><small>awaiting officer review</small></article></section>
    <section className="columns"><article className="panel mapPanel"><div className="panelHead"><div><span className="eyebrow">SPATIAL VIEW</span><h2>Risk cells</h2></div><span className="legend"><i /> Elevated</span></div>
      <div className="mapCanvas"><div className="mapGrid" />{hot.map((cell) => { const p = cell.properties; const ring = cell.geometry?.coordinates?.[0] || []; const lon = ring.reduce((sum: number, point: number[]) => sum + point[0], 0) / (ring.length || 1); const lat = ring.reduce((sum: number, point: number[]) => sum + point[1], 0) / (ring.length || 1); const left = Math.max(2, Math.min(98, ((lon - 91.55) / .4) * 100)); const top = Math.max(2, Math.min(98, ((26.35 - lat) / .4) * 100)); return <div key={p.cell_id} title={`${p.cell_id} · ${Math.round((p.risk_p || 0) * 100)}%`} className={`cell c${Math.min(4, Math.floor((p.risk_p || 0) * 5))}`} style={{ left: `${left}%`, top: `${top}%` }} />; })}<div className="mapLabel">ASSAM · DEMO GRID</div></div>
      <div className="tableHead"><span>Cell</span><span>State</span><span>Risk</span><span>Review</span></div>{hot.slice(0, 5).map((c) => <div className="tableRow" key={c.properties.cell_id}><b>{c.properties.cell_id}</b><span>{c.properties.state}</span><span>{c.properties.risk_p == null ? "—" : `${Math.round(c.properties.risk_p * 100)}%`}</span><span>{c.properties.risk_p >= .8 ? <button className="tableButton" onClick={() => startRun(c.properties.cell_id)}>{c.properties.synthetic ? "Draft demo" : "Draft alert"}</button> : c.properties.action || "No score"}</span></div>)}
    </article><article className="panel"><div className="panelHead"><div><span className="eyebrow">COMMUNITY SIGNAL</span><h2>Report review</h2></div><span className="count">{data.reports.length}</span></div>{data.reports.length ? data.reports.slice(0, 8).map((r) => <div className="reviewItem" key={r.id}><div className="itemTop"><b>{r.location_name || r.cell_id || "Location pending"}</b><small>{new Date(r.received_at).toLocaleString()}</small></div><img className="reportPhoto" src={`/api/report-photo/${encodeURIComponent(r.id)}`} alt="Volunteer submitted evidence" /><p>{r.note || "Photo report submitted"}</p><div className="flags">{(r.flags || []).map((f: string) => <span key={f}>{f.replaceAll("_", " ")}</span>)}</div><div className="buttonRow"><button onClick={() => review(r.id, "accepted")}>Accept</button><button className="secondary" onClick={() => review(r.id, "rejected")}>Reject</button></div></div>) : <p className="empty">No pending reports.</p>}</article></section>
    <section className="panel alertPanel"><div className="panelHead"><div><span className="eyebrow">HUMAN APPROVAL REQUIRED</span><h2>Alert drafts</h2></div><span className="count">{data.alerts.filter((a) => a.status === "draft").length}</span></div>{data.alerts.length ? data.alerts.map((a) => <div className="alertItem" key={a.id}><div><span className={`status ${a.status}`}>{a.status}</span>{a.facts?.synthetic && <span className="status synthetic">synthetic demo</span>}<b>{a.facts?.area_names?.join(", ") || a.run_id}</b><p>{a.texts?.en}</p><small>Risk {Math.round((a.facts?.risk_p || 0) * 100)}% · Valid until {a.facts?.valid_until ? new Date(a.facts.valid_until).toLocaleString() : "—"}</small></div>{a.status === "draft" && <div className="buttonRow"><button onClick={() => approve(a.id, true)}>Approve</button><button className="secondary" onClick={() => approve(a.id, false)}>Reject</button></div>}</div>) : <p className="empty">No alert drafts. High risk alerts require officer review before dispatch.</p>}</section>
    <footer>Liveslide · Early warning support · Synthetic data is labeled in the source system</footer></main>;
}
