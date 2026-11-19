import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const token = (await cookies()).get("liveslide_token")?.value;
  if (!token) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const { id } = await params;
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000/api/v1";
  const upstream = await fetch(`${base}/reports/${encodeURIComponent(id)}/photo`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
  if (!upstream.ok) return NextResponse.json({ error: "photo_unavailable" }, { status: upstream.status });
  return new NextResponse(await upstream.arrayBuffer(), { headers: { "Content-Type": upstream.headers.get("Content-Type") || "image/jpeg", "Cache-Control": "private, no-store" } });
}
