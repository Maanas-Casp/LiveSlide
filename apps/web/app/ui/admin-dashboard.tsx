"use client";

import { useState } from "react";

type User = { display_name: string; email: string };
type Data = { cells: any[]; reports: any[]; alerts: any[]; audit: any };

export default function AdminDashboard({ user, data: initial }: { user: User; data: Data }) {
  const [data, setData] = useState(initial);
  const [message, setMessage] = useState("");
  const [checking, setChecking] = useState(false);
  async function recheckAudit() {
    setChecking(true);
    const response = await fetch("/api/action?path=%2Faudit%2Fverify", { cache: "no-store" });
    if (response.ok) { setData({ ...data, audit: await response.json() }); setMessage("Audit chain checked."); }
    else setMessage("Could not check the audit chain.");
    setChecking(false);
  }
  async function logout() { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; }
  const pending = data.reports.filter((report) => report.status === "pending").length;
  const drafts = data.alerts.filter((alert) => alert.status === "draft").length;
  return <main className="appShell">
    <header className="topbar"><div className="brand"><span className="brandMark">L</span><span>Liveslide <small>ADMIN CONSOLE</small></span></div><div className="topActions"><span className="rolePill admin">ADMIN</span><button className="quiet" onClick={logout}>Sign out</button></div></header>
    <section className="pageHead"><div><div className="eyebrow">SYSTEM OVERSIGHT</div><h1>Good day, {user.display_name}</h1><p>Review platform activity, synthetic demo records, and audit integrity.</p></div><span className="date">Assam · current demo region</span></section>
    {message && <div className="notice">{message}<button onClick={() => setMessage("")}>×</button></div>}
    <section className="stats"><article><span>Mapped cells</span><strong>{data.cells.length}</strong><small>in current demo region</small></article><article><span>High risk cells</span><strong>{data.cells.filter((cell) => cell.properties?.risk_p >= .8).length}</strong><small>score at or above 0.80</small></article><article><span>All reports</span><strong>{data.reports.length}</strong><small>{pending} pending officer review</small></article><article><span>Alert drafts</span><strong>{drafts}</strong><small>awaiting officer approval</small></article></section>
    <section className="adminGrid">
      <article className="panel auditPanel"><div className="panelHead"><div><span className="eyebrow">INTEGRITY CHECK</span><h2>Append-only audit chain</h2></div><span className={`status ${data.audit?.valid ? "approved" : "rejected"}`}>{data.audit?.valid ? "valid" : "check needed"}</span></div>
        <p>{data.audit?.valid ? `${data.audit.rows_checked} recorded actions verified.` : "The audit chain could not be verified."}</p><button onClick={recheckAudit} disabled={checking}>{checking ? "Checking…" : "Run check again"}</button>
      </article>
      <article className="panel"><div className="panelHead"><div><span className="eyebrow">ROLE BOUNDARY</span><h2>Officer actions</h2></div></div><p className="empty">Report decisions and alert approvals stay with officer accounts. Admin accounts can inspect records and audit status.</p></article>
    </section>
    <section className="panel"><div className="panelHead"><div><span className="eyebrow">LATEST RECORDS</span><h2>Community reports</h2></div><span className="count">{data.reports.length}</span></div>
      {data.reports.length ? data.reports.slice(0, 8).map((report) => <div className="adminReport" key={report.id}><img src={`/api/report-photo/${encodeURIComponent(report.id)}`} alt="Submitted report evidence" /><div><div className="itemTop"><b>{report.location_name || report.cell_id || "Location pending"}</b><span className={`status ${report.status}`}>{report.status}</span></div><p>{report.note || "Photo report"}</p><small>{new Date(report.received_at).toLocaleString()} · {report.synthetic ? "Synthetic demo" : "Field submission"}</small></div></div>) : <p className="empty">No reports received.</p>}
    </section>
    <section className="panel"><div className="panelHead"><div><span className="eyebrow">ALERT REGISTER</span><h2>Draft and approved alerts</h2></div><span className="count">{data.alerts.length}</span></div>
      {data.alerts.length ? data.alerts.slice(0, 8).map((alert) => <div className="adminAlert" key={alert.id}><span className={`status ${alert.status}`}>{alert.status}</span>{alert.facts?.synthetic && <span className="status synthetic">synthetic demo</span>}<b>{alert.facts?.area_names?.join(", ") || alert.run_id}</b><span>Risk {Math.round((alert.facts?.risk_p || 0) * 100)}%</span><small>{alert.texts?.en}</small></div>) : <p className="empty">No alerts created yet. High risk demo alerts can be drafted in the officer desk.</p>}
    </section>
    <footer>Liveslide · Admin view · Officer decisions remain separately authorized.</footer>
  </main>;
}
