import { useState } from "react";
import {
  Building2,
  ClipboardCheck,
  ArrowRight,
  ShieldCheck,
  Activity,
} from "lucide-react";
import { api, setCSRF, human, type Session } from "../api";
import { ErrorBox } from "../components/ui";

export default function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [role, setRole] = useState("admin");
  async function login(email: string, password: string) {
    setBusy(true);
    setError("");
    try {
      const s = await api<Session>("/auth/login", "POST", { email, password });
      setCSRF(s.csrf_token);
      onLogin(s);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-shell">
      <section className="login-story">
        <div className="brand">
          <div className="brand-icon">
            <Building2 size={25} />
          </div>
          <span>
            Permits<span style={{ color: "#ff9a70" }}>NJ</span>
          </span>
        </div>
        <div>
          <span className="demo-pill">MUNICIPAL WORKSPACE</span>
          <h1>
            Better communities.
            <br />
            One permit at a time.
          </h1>
          <p>
            A clearer path from application to approval. Manage your
            municipality’s permits, reviews, and inspections in one place.
          </p>
          <div className="login-features">
            <span>
              <ShieldCheck />
              Purposeful access controls
            </span>
            <span>
              <ClipboardCheck />
              Connected permit workflows
            </span>
            <span>
              <Activity />
              Every important change recorded
            </span>
          </div>
        </div>
        <small>Built for the people who keep communities moving.</small>
      </section>
      <section className="login-panel">
        <div className="login-card">
          <span className="eyebrow">WELCOME TO PERMITSNJ</span>
          <h2>Sign in to your workspace</h2>
          <p className="subtitle">
            Choose a demonstration role or sign in below.
          </p>
          <div className="banner">
            <ShieldCheck size={21} />
            <span>
              <strong>Demonstration environment</strong>
              <br />
              Synthetic records. Mock payments. No government services.
            </span>
          </div>
          <label htmlFor="demo-role">Explore as</label>
          <select
            id="demo-role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            {[
              "admin",
              "clerk",
              "reviewer",
              "inspector",
              "applicant",
              "other",
            ].map((r) => (
              <option key={r} value={r}>
                {r === "other" ? "Other municipality admin" : human(r)}
              </option>
            ))}
          </select>
          <button
            className="button primary"
            disabled={busy}
            onClick={() =>
              login(`${role}@demo.permitsnj.test`, "DemoPermit2026!")
            }
          >
            Enter demo workspace
            <ArrowRight size={17} />
          </button>
          <p className="help-text">
            Demo access requires the server’s explicit DEMO_MODE setting.
          </p>
          <div className="login-divider">or sign in with an account</div>
          <ErrorBox message={error} />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const d = new FormData(e.currentTarget);
              void login(String(d.get("email")), String(d.get("password")));
            }}
          >
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                required
                placeholder="you@municipality.gov"
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
              />
            </div>
            <button className="button secondary" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="help-text">
            Need access? Contact your municipality administrator.
          </p>
        </div>
      </section>
    </div>
  );
}
