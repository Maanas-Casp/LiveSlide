import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET(request: NextRequest) { return forward(request); }
export async function POST(request: NextRequest) { return forward(request); }
export async function PATCH(request: NextRequest) { return forward(request); }
async function forward(request: NextRequest) {
  const token = (await cookies()).get("liveslide_token")?.value;
  if (!token) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const path = request.nextUrl.searchParams.get("path") || "";
  if (!path.startsWith("/") || path.includes("..")) return NextResponse.json({ error: "invalid_path" }, { status: 400 });
  const base = process.env.API_INTERNAL_URL || "http://localhost:8000/api/v1";
  const upstream = await fetch(`${base}${path}`, { method: request.method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: request.method === "GET" ? undefined : await request.text(), cache: "no-store" });
  return new NextResponse(await upstream.text(), { status: upstream.status, headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" } });
}
