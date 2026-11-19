"use client";

import { FormEvent, useState } from "react";

type User = { display_name: string; email: string };
type Report = { id: string; cell_id: string | null; location_name: string | null; received_at: string; captured_at: string; status: string; note?: string; flags: string[]; synthetic: boolean };

export default function VolunteerDashboard({ user, reports: initial }: { user: User; reports: Report[] }) {
  const [reports, setReports] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [position, setPosition] = useState({ lat: "", lon: "" });
  const [locationName, setLocationName] = useState("");
  const [locationStatus, setLocationStatus] = useState("Location permission has not been requested.");

  async function locate() {
    if (!navigator.geolocation) { setLocationStatus("This browser cannot share device location. Enter a place name below."); return; }
    setLocationStatus("Waiting for device location permission…");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setPosition({ lat: coords.latitude.toFixed(6), lon: coords.longitude.toFixed(6) });
        setLocationStatus("Device location attached.");
      },
      (error) => {
        const reason = error.code === error.PERMISSION_DENIED ? "Location permission was denied."
          : error.code === error.TIMEOUT ? "The location request timed out."
            : "The device could not determine its location.";
        setLocationStatus(`${reason} Enter a place name below to continue.`);
      },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setMessage("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const place = String(form.get("location_name") || "").trim();
    if ((!position.lat || !position.lon) && !place) {
      setBusy(false);
      setMessage("Add a place, village, road or landmark, or allow device location.");
      return;
    }
    form.set("location_name", place);
    if (!position.lat || !position.lon) { form.delete("lat"); form.delete("lon"); }
    form.set("client_report_id", crypto.randomUUID());
    form.set("device_id", "liveslide-web");
    form.set("captured_at", new Date(String(form.get("captured_at"))).toISOString());
    try {
      const response = await fetch("/api/report-upload", { method: "POST", body: form });
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload?.error?.message || payload?.detail || "Report upload failed.");
      }
      const listResponse = await fetch("/api/action?path=%2Freports", { cache: "no-store" });
      if (listResponse.ok) setReports(await listResponse.json());
      formElement.reset(); setPosition({ lat: "", lon: "" }); setLocationName("");
      setLocationStatus("Location permission has not been requested.");
      setMessage("Report submitted. It is now in your report history.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not submit the report.");
    } finally { setBusy(false); }
  }

  async function logout() { await fetch("/api/logout", { method: "POST" }); location.href = "/login"; }

  return <main className="appShell">
    <header className="topbar"><div className="brand"><span className="brandMark">L</span><span>Liveslide <small>COMMUNITY REPORTER</small></span></div><div className="topActions"><span className="rolePill">VOLUNTEER</span><button className="quiet" onClick={logout}>Sign out</button></div></header>
    <section className="pageHead"><div><div className="eyebrow">FIELD REPORTING</div><h1>Hello, {user.display_name}</h1><p>Submit a photo and location when you observe possible landslide activity.</p></div><span className="date">Reports go to an officer for review</span></section>
    {message && <div className="notice">{message}<button onClick={() => setMessage("")}>×</button></div>}
    <section className="volunteerGrid">
      <article className="panel"><div className="panelHead"><div><span className="eyebrow">NEW SUBMISSION</span><h2>Report what you see</h2></div><span className="status">OFFICER REVIEW</span></div>
        <form className="reportForm" onSubmit={submit}>
          <label>Photo evidence<input name="photo" type="file" accept="image/jpeg,image/png" capture="environment" required /></label>
          <label>Short description <small>(optional)</small><textarea name="note" maxLength={500} rows={3} placeholder="Describe the visible condition or damage" /></label>
          <div className="formSectionHead"><b>Where did you see it?</b><button type="button" className="secondary" onClick={locate}>Use my device location</button></div>
          <label>Place, village, road or nearby landmark<input name="location_name" value={locationName} onChange={(e) => setLocationName(e.target.value)} maxLength={300} placeholder="For example: near Mawkdok market, Sohra" required={!position.lat || !position.lon} /></label>
          <small className="locationHelp" aria-live="polite">{locationStatus} You can submit with a place name even if GPS is unavailable; an officer will verify it.</small>
          <details className="coordinateDetails"><summary>Enter coordinates manually (optional)</summary><div className="formRow"><label>Latitude<input name="lat" type="number" step="any" value={position.lat} onChange={(e) => setPosition({ ...position, lat: e.target.value })} /></label><label>Longitude<input name="lon" type="number" step="any" value={position.lon} onChange={(e) => setPosition({ ...position, lon: e.target.value })} /></label></div></details>
          <label>Observed at<input name="captured_at" type="datetime-local" defaultValue={new Date().toISOString().slice(0, 16)} required /></label>
          <button disabled={busy}>{busy ? "Submitting…" : "Submit report"}</button>
        </form>
      </article>
      <article className="panel"><div className="panelHead"><div><span className="eyebrow">YOUR ACTIVITY</span><h2>Report history</h2></div><span className="count">{reports.length}</span></div>
        {reports.length ? reports.map((report) => <div className="volunteerReport" key={report.id}>
          <img src={`/api/report-photo/${encodeURIComponent(report.id)}`} alt="Your submitted photo" />
          <div className="volunteerReportBody"><div className="itemTop"><b>{report.location_name || report.cell_id || "Location pending"}</b><span className={`status ${report.status}`}>{report.status}</span></div>
            <p>{report.note || "Photo report"}</p><small>Submitted {new Date(report.received_at).toLocaleString()}</small>
            {report.synthetic && <span className="status synthetic">synthetic demo</span>}
          </div>
        </div>) : <p className="empty">Your submitted reports will appear here.</p>}
      </article>
    </section>
    <footer>Liveslide · Your report is shared with authorized officers for verification.</footer>
  </main>;
}
