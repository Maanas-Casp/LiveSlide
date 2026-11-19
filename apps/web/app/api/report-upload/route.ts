import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(request: NextRequest) {
  const token = (await cookies()).get("liveslide_token")?.value;
  if (!token) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const form = await request.formData();
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000/api/v1";
  const upstream = await fetch(`${base}/reports`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form, cache: "no-store",
  });
  const payload = await upstream.json();
  return NextResponse.json(payload, { status: upstream.status });
}
