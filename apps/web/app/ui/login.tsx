"use client";

import { FormEvent, useState } from "react";

export default function Login() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const response = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
    if (response.ok) location.href = "/";
    else { setError("Sign-in failed. Check your email and password."); setBusy(false); }
  }
  return <main className="loginShell"><form className="loginCard" onSubmit={submit}>
    <div className="eyebrow">LIVESLIDE · FIELD INTELLIGENCE</div><h1>Sign in</h1>
    <p>Your workspace opens based on your account role.</p>
    <label>Email<input name="email" type="email" autoComplete="username" required placeholder="officer@example.test" /></label>
    <label>Password<input name="password" type="password" autoComplete="current-password" required /></label>
    {error && <div className="error">{error}</div>}<button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    <small>Demo: officer@example.test · volunteer@example.test · admin@example.test<br />All demo accounts use password: liveslide-dev</small>
  </form></main>;
}
