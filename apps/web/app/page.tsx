import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import AdminDashboard from "./ui/admin-dashboard";
import Dashboard from "./ui/dashboard";
import VolunteerDashboard from "./ui/volunteer-dashboard";

export default async function Home() {
  const token = (await cookies()).get("liveslide_token")?.value;
  if (!token) redirect("/login");
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000/api/v1";
  const headers = { Authorization: `Bearer ${token}` };
  const meResponse = await fetch(`${base}/auth/me`, { headers, cache: "no-store" });
  if (!meResponse.ok) redirect("/login");
  const user = await meResponse.json();
  if (user.role === "volunteer") {
    const reportsResponse = await fetch(`${base}/reports`, { headers, cache: "no-store" });
    return <VolunteerDashboard user={user} reports={reportsResponse.ok ? await reportsResponse.json() : []} />;
  }
  if (user.role === "admin") {
    const [cellsResponse, reportsResponse, alertsResponse, auditResponse] = await Promise.all([
      fetch(`${base}/cells?bbox=91.55,25.95,91.95,26.35&limit=500`, { headers, cache: "no-store" }),
      fetch(`${base}/reports`, { headers, cache: "no-store" }),
      fetch(`${base}/alerts`, { headers, cache: "no-store" }),
      fetch(`${base}/audit/verify`, { headers, cache: "no-store" }),
    ]);
    return <AdminDashboard user={user} data={{
      cells: cellsResponse.ok ? (await cellsResponse.json()).features : [],
      reports: reportsResponse.ok ? await reportsResponse.json() : [],
      alerts: alertsResponse.ok ? await alertsResponse.json() : [],
      audit: auditResponse.ok ? await auditResponse.json() : null,
    }} />;
  }
  const [cellsResponse, alertsResponse, reportsResponse] = await Promise.all([
    fetch(`${base}/cells?bbox=91.55,25.95,91.95,26.35&limit=500`, { headers, cache: "no-store" }),
    fetch(`${base}/alerts`, { headers, cache: "no-store" }),
    fetch(`${base}/reports?status=pending`, { headers, cache: "no-store" }),
  ]);
  const data = {
    cells: cellsResponse.ok ? (await cellsResponse.json()).features : [],
    alerts: alertsResponse.ok ? await alertsResponse.json() : [],
    reports: reportsResponse.ok ? await reportsResponse.json() : [],
  };
  return <Dashboard initial={data} />;
}
