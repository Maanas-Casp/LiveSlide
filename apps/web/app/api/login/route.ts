import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const { email, password } = await request.json();
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000/api/v1";
  const upstream = await fetch(`${base}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }), cache: "no-store" });
  if (!upstream.ok) return NextResponse.json({ error: "invalid_credentials" }, { status: upstream.status });
  const data = await upstream.json();
  const response = NextResponse.json({ role: data.role, display_name: data.display_name });
  response.cookies.set("liveslide_token", data.access_token, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 3600 });
  return response;
}
