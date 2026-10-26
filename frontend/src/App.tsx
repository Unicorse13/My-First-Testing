import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  LayoutDashboard,
  FileText,
  Users,
  HardHat,
  Building2,
  CreditCard,
  ClipboardCheck,
  CalendarCheck,
  FileBadge,
  TriangleAlert,
  ChartNoAxesCombined,
  Search,
  Plus,
  ArrowUpRight,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Menu,
  X,
  LogOut,
  Bell,
  HelpCircle,
  Download,
  Printer,
  Check,
  Clock,
  ShieldCheck,
  Activity,
  FolderOpen,
  RefreshCw,
} from "lucide-react";
import Fees from "./Fees";
import {
  api,
  setCSRF,
  text,
  money,
  human,
  date,
  type User,
  type Session,
  type Config,
  type Row,
  type Permit,
} from "./api";
const navigation = [
  ["Dashboard", LayoutDashboard],
  ["Permits", FileText],
  ["Applicants", Users],
  ["Contractors", HardHat],
  ["Municipalities", Building2],
  ["Payments", CreditCard],
  ["Plan Reviews", ClipboardCheck],
  ["Inspections", CalendarCheck],
  ["Certificates", FileBadge],
  ["Notices & Orders", TriangleAlert],
  ["Reports", ChartNoAxesCombined],
  ["Fees & Setup", Building2],
] as const;
const staffRoles = ["admin", "clerk", "reviewer", "inspector"];
function isRole(user: User, ...roles: string[]) {
  return roles.includes(user.role);
}
function Badge({ value }: { value: unknown }) {
  return (
    <span
      className={`status ${text(value).toLowerCase().replaceAll(" ", "_")}`}
    >
      {human(value)}
    </span>
  );
}
function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div className="alert error" role="alert">
      <TriangleAlert size={17} />
      {message}
    </div>
  ) : null;
}
function Empty({
  message = "No records found. Try a different search or create a new record.",
}: {
  message?: string;
}) {
  return (
    <div className="empty-state">
      <FolderOpen size={32} />
      <h3>Nothing here yet</h3>
      <p>{message}</p>
    </div>
  );
}
function Loading() {
  return (
    <div role="status" className="empty-state">
      <RefreshCw className="spin" size={25} />
      <p>Loading your workspace…</p>
    </div>
  );
}
function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const root = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const key = (e: KeyboardEvent) => {
      const dialogs = document.querySelectorAll('[role="dialog"]');
      if (dialogs[dialogs.length - 1] !== root.current) return;
      if (e.key === "Escape") closeRef.current();
      if (e.key === "Tab") {
        const els = root.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href]",
        );
        if (!els?.length) return;
        const first = els[0],
          last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    root.current?.querySelector<HTMLElement>("button,input")?.focus();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = before;
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={root}
      >
        <div className="modal-header">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
interface Field {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: { value: string | number; label: string }[];
  help?: string;
  value?: string | number | boolean;
  min?: number;
  max?: number;
  step?: string;
  wide?: boolean;
}
function Form({
  fields,
  submitLabel = "Save changes",
  onSubmit,
  onCancel,
  children,
}: {
  fields: Field[];
  submitLabel?: string;
  onSubmit: (values: Record<string, string | boolean>) => Promise<void>;
  onCancel?: () => void;
  children?: ReactNode;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <form
      onSubmit={async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const d = new FormData(e.currentTarget);
        const values: Record<string, string | boolean> = {};
        for (const f of fields)
          values[f.name] =
            f.type === "checkbox" ? d.has(f.name) : String(d.get(f.name) || "");
        setBusy(true);
        setError("");
        try {
          await onSubmit(values);
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="modal-body">
        <ErrorBox message={error} />
        <div className="form-grid">
          {fields.map((f) => (
            <div className={`field ${f.wide ? "field-wide" : ""}`} key={f.name}>
              {f.type === "checkbox" ? (
                <label className="checkbox-row">
                  <input
                    name={f.name}
                    type="checkbox"
                    defaultChecked={Boolean(f.value)}
                  />
                  {f.label}
                </label>
              ) : (
                <>
                  <label htmlFor={`field-${f.name}`}>
                    {f.label}
                    {f.required && <span aria-label=" required"> *</span>}
                  </label>
                  {f.options ? (
                    <select
                      id={`field-${f.name}`}
                      name={f.name}
                      required={f.required}
                      defaultValue={String(f.value ?? "")}
                    >
                      <option value="">Select an option</option>
                      {f.options.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  ) : f.type === "textarea" ? (
                    <textarea
                      id={`field-${f.name}`}
                      name={f.name}
                      required={f.required}
                      defaultValue={String(f.value ?? "")}
                      rows={3}
                      maxLength={2000}
                    />
                  ) : (
                    <input
                      id={`field-${f.name}`}
                      name={f.name}
                      type={f.type || "text"}
                      required={f.required}
                      defaultValue={String(f.value ?? "")}
                      min={f.min}
                      max={f.max}
                      step={f.step}
                      maxLength={f.type === "number" ? undefined : 300}
                    />
                  )}
                </>
              )}
              {f.help && <small className="help-text">{f.help}</small>}
            </div>
          ))}
        </div>
        {children}
      </div>
      <div className="modal-footer">
        {onCancel && (
          <button type="button" className="button secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button disabled={busy} className="button primary" type="submit">
          {busy ? "Saving…" : submitLabel}
          <ArrowRight size={16} />
        </button>
      </div>
    </form>
  );
}
function Login({ onLogin }: { onLogin: (s: Session) => void }) {
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
export default function App() {
  const [session, setSession] = useState<Session | null>(null),
    [ready, setReady] = useState(false),
    [config, setConfig] = useState<Config | null>(null),
    [page, setPage] = useState("Dashboard"),
    [open, setOpen] = useState(false),
    [permitId, setPermitId] = useState<number | null>(null),
    [create, setCreate] = useState(false),
    [refresh, setRefresh] = useState(0),
    [toast, setToast] = useState(""),
    [support, setSupport] = useState(false),
    [globalError, setGlobalError] = useState("");
  useEffect(() => {
    api<Session>("/auth/me")
      .then((s) => {
        setCSRF(s.csrf_token);
        setSession(s);
      })
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);
  useEffect(() => {
    let active = true;
    if (session)
      api<Config>("/config")
        .then((value) => {
          if (active) setConfig(value);
        })
        .catch((e) => {
          if (active) setGlobalError(e.message);
        });
    else setConfig(null);
    return () => {
      active = false;
    };
  }, [session, refresh]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(t);
  }, [toast]);
  function changed(message = "Changes saved") {
    setRefresh((x) => x + 1);
    setToast(message);
  }
  function changeSession(next: Session | null) {
    setConfig(null);
    setPage("Dashboard");
    setPermitId(null);
    setCreate(false);
    setSupport(false);
    setOpen(false);
    setGlobalError("");
    setToast("");
    setSession(next);
  }
  if (!ready) return <Loading />;
  if (!session) return <Login onLogin={changeSession} />;
  const user = session.user,
    staff = staffRoles.includes(user.role);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      {open && <div className="mobile-scrim" onClick={() => setOpen(false)} />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <a
          href="#dashboard"
          className="brand"
          onClick={() => setPage("Dashboard")}
        >
          <div className="brand-icon">
            <Building2 size={23} />
          </div>
          <span>
            Permits<span style={{ color: "#ffa279" }}>NJ</span>
          </span>
        </a>
        <div className="municipality-switch">
          <span className="municipality-symbol">
            <Building2 size={18} />
          </span>
          <span>
            <small>YOUR MUNICIPALITY</small>
            <strong>
              {(config?.municipalities.find(
                (m) => m.id === user.municipality_id,
              )?.name as string) || "Municipal workspace"}
            </strong>
          </span>
          <ChevronDown size={15} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav className="nav" aria-label="Main navigation">
          {navigation
            .filter(
              ([name]) =>
                staff ||
                !["Reports", "Plan Reviews", "Fees & Setup"].includes(name),
            )
            .map(([name, Icon]) => (
              <button
                key={name}
                className={`nav-item ${page === name ? "active" : ""}`}
                onClick={() => {
                  setPage(name);
                  setOpen(false);
                }}
              >
                <Icon size={19} />
                <span>{name}</span>
                {name === "Permits" && <span className="nav-count">↗</span>}
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="demo-sidebar">
            <span className="demo-dot" />
            Demo environment<small>Synthetic data · No real transactions</small>
          </div>
          <button className="nav-item" onClick={() => setSupport(true)}>
            <HelpCircle size={18} />
            <span>Help & feedback</span>
          </button>
          <div className="user-profile">
            <span className="avatar">
              {user.name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <span>
              <strong>{user.name}</strong>
              <small>{human(user.role)}</small>
            </span>
            <button
              className="icon-button"
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await api("/auth/logout", "POST", {});
                  changeSession(null);
                } catch (e) {
                  setGlobalError((e as Error).message);
                }
              }}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setOpen(!open)}
            >
              <Menu />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <div className="topbar-actions">
            <span className="demo-pill">DEMO</span>
            <span className="topbar-date">
              {new Date().toLocaleDateString("en-US", {
                weekday: "short",
                month: "short",
                day: "numeric",
              })}
            </span>
            <button
              className="icon-button"
              aria-label="Workspace guidance"
              onClick={() => setSupport(true)}
            >
              <Bell size={19} />
            </button>
            <span className="avatar small">{user.name[0]}</span>
          </div>
        </header>
        <main className="content" id="main-content">
          <ErrorBox message={globalError} />
          {!config ? (
            <Loading />
          ) : page === "Dashboard" ? (
            <Dashboard
              user={user}
              refresh={refresh}
              onPermit={setPermitId}
              navigate={setPage}
              onCreate={() => setCreate(true)}
            />
          ) : page === "Permits" ? (
            <Permits
              config={config}
              refresh={refresh}
              onPermit={setPermitId}
              onCreate={() => setCreate(true)}
              user={user}
            />
          ) : ["Applicants", "Contractors", "Municipalities"].includes(page) ? (
            <Directory
              page={page}
              user={user}
              refresh={refresh}
              changed={changed}
            />
          ) : page === "Fees & Setup" ? (
            <Fees user={user} />
          ) : page === "Reports" ? (
            <Reports config={config} />
          ) : (
            <WorkflowList
              page={page}
              user={user}
              refresh={refresh}
              onPermit={setPermitId}
              changed={changed}
            />
          )}
        </main>
        <footer className="footer">
          <span>PermitsNJ · Municipal workspace</span>
          <span>
            Demonstration application · Sample rules, not legal guidance
          </span>
        </footer>
      </div>
      {toast && (
        <div className="toast-container">
          <div className="toast" role="status">
            <Check size={18} />
            {toast}
          </div>
        </div>
      )}
      {create && config && (
        <PermitForm
          config={config}
          onClose={() => setCreate(false)}
          onSaved={(id) => {
            setCreate(false);
            changed("Permit application created");
            setPermitId(id);
          }}
        />
      )}
      {permitId !== null && config && (
        <PermitDetail
          id={permitId}
          user={user}
          config={config}
          onClose={() => setPermitId(null)}
          changed={changed}
        />
      )}{" "}
      {support && (
        <Modal title="Help & feedback" onClose={() => setSupport(false)}>
          <div className="modal-body support-panel">
            <HelpCircle size={34} />
            <h3>Your municipal workspace, explained.</h3>
            <p>
              Start with a permit, confirm prior approvals, and follow its
              progress through plan review, payment, issuance, and inspection.
              Each role has a different set of actions.
            </p>
            <p>
              <strong>This is a demonstration.</strong> Fees are sample rules;
              payments are simulated and documents are not official municipal
              forms.
            </p>
            <p>
              For account access or feedback, contact the administrator
              operating this deployment. No email or support service is
              connected.
            </p>
            <button
              className="button secondary"
              onClick={() => {
                setSupport(false);
                setPage("Permits");
              }}
            >
              Explore permits
              <ArrowRight size={16} />
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
function Heading({
  eyebrow = "MUNICIPAL WORKSPACE",
  title,
  subtitle,
  children,
}: {
  eyebrow?: string;
  title: string;
  subtitle: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
function Dashboard({
  user,
  refresh,
  onPermit,
  navigate,
  onCreate,
}: {
  user: User;
  refresh: number;
  onPermit: (id: number) => void;
  navigate: (s: string) => void;
  onCreate: () => void;
}) {
  const [data, setData] = useState<{
      permit_count: number;
      open_count: number;
      outstanding_cents: number;
      inspections_due: number;
      recent_permits: Permit[];
    } | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    api<typeof data>("/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, [refresh]);
  return (
    <>
      <Heading
        eyebrow="YOUR COMMUNITY, AT A GLANCE"
        title={`Welcome back, ${user.name.split(" ")[0]}.`}
        subtitle="Here’s what’s happening across your permit workspace."
      >
        {isRole(user, "admin", "clerk", "applicant") && (
          <button className="button primary" onClick={onCreate}>
            <Plus size={18} />
            New permit
          </button>
        )}
      </Heading>
      <div className="banner">
        <span className="banner-icon">
          <ShieldCheck size={20} />
        </span>
        <span>
          <strong>A safe place to explore.</strong> You’re viewing synthetic
          demonstration records. Payments are simulated and fee schedules are
          examples.
        </span>
        <span className="demo-pill">DEMO DATA</span>
      </div>
      <ErrorBox message={error} />
      {!data ? (
        <Loading />
      ) : (
        <>
          <div className="stats-grid">
            {[
              {
                label: "Total permits",
                value: data.permit_count,
                icon: FileText,
                footer: "All applications in your workspace",
                tone: "orange",
              },
              {
                label: "Open applications",
                value: data.open_count,
                icon: Clock,
                footer: "Moving through the permit process",
                tone: "blue",
              },
              {
                label: "Outstanding balance",
                value: money(data.outstanding_cents),
                icon: CreditCard,
                footer: "Assessed fees less mock payments",
                tone: "purple",
              },
              {
                label: "Inspections due",
                value: data.inspections_due,
                icon: CalendarCheck,
                footer: "Scheduled and awaiting a result",
                tone: "green",
              },
            ].map((s) => (
              <div className="stat-card" key={s.label}>
                <div className="stat-label">
                  {s.label}
                  <span className={`stat-icon ${s.tone}`}>
                    <s.icon size={19} />
                  </span>
                </div>
                <div className="stat-value">{s.value}</div>
                <div className="stat-footer">{s.footer}</div>
              </div>
            ))}
          </div>
          <div className="dashboard-grid">
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Recent permit activity</h2>
                  <p className="panel-subtitle">
                    The latest applications and updates
                  </p>
                </div>
                <button
                  className="button ghost small"
                  onClick={() => navigate("Permits")}
                >
                  View all permits
                  <ArrowUpRight size={16} />
                </button>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>PERMIT / PROJECT</th>
                      <th>TYPE</th>
                      <th>STATUS</th>
                      <th>UPDATED</th>
                      <th aria-label="Open" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_permits.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <button
                            className="table-link"
                            onClick={() => onPermit(p.id)}
                          >
                            {p.number}
                          </button>
                          <small>{p.work_address}</small>
                        </td>
                        <td>{human(p.type)}</td>
                        <td>
                          <Badge value={p.status} />
                        </td>
                        <td className="muted">{date(p.updated_at)}</td>
                        <td>
                          <button
                            className="icon-button"
                            aria-label={`Open ${p.number}`}
                            onClick={() => onPermit(p.id)}
                          >
                            <ArrowUpRight size={17} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!data.recent_permits.length && <Empty />}
              </div>
            </section>
            <aside className="panel quick-panel">
              <div className="panel-header">
                <div>
                  <h2 className="panel-title">Keep things moving</h2>
                  <p className="panel-subtitle">Your everyday shortcuts</p>
                </div>
              </div>
              <div className="quick-actions">
                {[
                  {
                    title: "Start an application",
                    subtitle: "Create a new permit record",
                    icon: Plus,
                    action: onCreate,
                  },
                  {
                    title: "Review inspections",
                    subtitle: "Schedules, results & follow-ups",
                    icon: CalendarCheck,
                    action: () => navigate("Inspections"),
                  },
                  {
                    title: "Track payments",
                    subtitle: "Mock receipts and balances",
                    icon: CreditCard,
                    action: () => navigate("Payments"),
                  },
                ]
                  .filter(
                    (a) =>
                      a.title !== "Start an application" ||
                      isRole(user, "admin", "clerk", "applicant"),
                  )
                  .map((a) => (
                    <button
                      className="action-tile"
                      key={a.title}
                      onClick={a.action}
                    >
                      <span className="action-icon">
                        <a.icon size={20} />
                      </span>
                      <span>
                        <strong>{a.title}</strong>
                        <small>{a.subtitle}</small>
                      </span>
                      <ChevronRight size={17} />
                    </button>
                  ))}
              </div>
              <div className="workflow-note">
                <span className="eyebrow">A CLEARER PATH TO APPROVAL</span>
                <h3>Every step, connected.</h3>
                <p>
                  From the first application to the final certificate, keep the
                  complete project story in one place.
                </p>
                <div className="workflow-dots">
                  <span />
                  <i />
                  <span />
                  <i />
                  <span />
                  <i />
                  <span />
                </div>
              </div>
            </aside>
          </div>
          <section className="workspace-tip">
            <span className="tip-icon">
              <ClipboardCheck />
            </span>
            <div>
              <h3>Your workflow, with a record of every step</h3>
              <p>
                Applications, decisions, payments, and inspection results are
                linked to the permit and recorded in its audit history.
              </p>
            </div>
            <button
              className="button secondary small"
              onClick={() => navigate("Permits")}
            >
              Open permits
              <ArrowRight size={16} />
            </button>
          </section>
        </>
      )}
    </>
  );
}
function Permits({
  config,
  refresh,
  onPermit,
  onCreate,
  user,
}: {
  config: Config;
  refresh: number;
  onPermit: (id: number) => void;
  onCreate: () => void;
  user: User;
}) {
  const [q, setQ] = useState(""),
    [status, setStatus] = useState(""),
    [type, setType] = useState(""),
    [sort, setSort] = useState("updated_at"),
    [direction, setDirection] = useState("desc"),
    [page, setPage] = useState(1),
    [data, setData] = useState<{
      items: Permit[];
      total: number;
      page_size: number;
    } | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    const t = setTimeout(() => {
      api<typeof data>(
        `/permits?${new URLSearchParams({ q, status, type, sort, direction, page: String(page), page_size: "10" })}`,
      )
        .then((d) => {
          if (!controller.signal.aborted) setData(d);
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        });
    }, 200);
    return () => {
      clearTimeout(t);
      controller.abort();
    };
  }, [q, status, type, sort, direction, page, refresh]);
  return (
    <>
      <Heading
        title="Permits"
        subtitle={
          user.role === "applicant"
            ? "Track and manage your permit applications."
            : "Every application, from submission to completion."
        }
      >
        {isRole(user, "admin", "clerk", "applicant") && (
          <button className="button primary" onClick={onCreate}>
            <Plus size={18} />
            New permit
          </button>
        )}
      </Heading>
      <section className="panel">
        <div className="table-toolbar">
          <div className="search-field">
            <Search size={18} />
            <input
              aria-label="Search permits"
              placeholder="Search permit number, address, or applicant…"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <div className="filters">
            <select
              aria-label="Filter by status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              {config.statuses.map((s) => (
                <option key={text(s.code)} value={text(s.code)}>
                  {text(s.label)}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by permit type"
              value={type}
              onChange={(e) => {
                setType(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All permit types</option>
              {config.permit_types.map((t) => (
                <option key={text(t.code)} value={text(t.code)}>
                  {text(t.label)}
                </option>
              ))}
            </select>
            <select
              aria-label="Sort permits"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="updated_at">Last updated</option>
              <option value="number">Permit number</option>
              <option value="created_at">Date created</option>
              <option value="status">Status</option>
            </select>
            <button
              className="icon-button"
              title="Reverse sort order"
              aria-label="Reverse sort order"
              onClick={() =>
                setDirection(direction === "desc" ? "asc" : "desc")
              }
            >
              {direction === "desc" ? "↓" : "↑"}
            </button>
          </div>
        </div>
        <ErrorBox message={error} />
        {!data ? (
          <Loading />
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>PERMIT / ADDRESS</th>
                    <th>APPLICANT</th>
                    <th>TYPE</th>
                    <th>STATUS</th>
                    <th>BALANCE</th>
                    <th>UPDATED</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <button
                          className="table-link"
                          onClick={() => onPermit(p.id)}
                        >
                          {p.number}
                        </button>
                        <small>{p.work_address}</small>
                      </td>
                      <td>{p.applicant_name}</td>
                      <td>{human(p.type)}</td>
                      <td>
                        <Badge value={p.status} />
                      </td>
                      <td className="amount">{money(p.balance_cents)}</td>
                      <td className="muted">{date(p.updated_at)}</td>
                      <td>
                        <button
                          className="icon-button"
                          aria-label={`View ${p.number}`}
                          onClick={() => onPermit(p.id)}
                        >
                          <ArrowUpRight size={17} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.items.length && <Empty />}
            </div>
            <div className="pagination">
              <span>
                {data.total
                  ? `${(page - 1) * 10 + 1}–${Math.min(page * 10, data.total)} of ${data.total} permits`
                  : "0 permits"}
              </span>
              <div>
                <button
                  className="icon-button"
                  aria-label="Previous page"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft size={18} />
                </button>
                <span>Page {page}</span>
                <button
                  className="icon-button"
                  aria-label="Next page"
                  disabled={page * 10 >= data.total}
                  onClick={() => setPage(page + 1)}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}
function PermitForm({
  config,
  permit,
  onClose,
  onSaved,
}: {
  config: Config;
  permit?: Permit;
  onClose: () => void;
  onSaved: (id: number) => void;
}) {
  const [applicants, setApplicants] = useState<Row[]>([]),
    [contractors, setContractors] = useState<Row[]>([]),
    [loaded, setLoaded] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Row[]>("/applicants"), api<Row[]>("/contractors")])
      .then(([a, c]) => {
        setApplicants(a);
        setContractors(c);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, []);
  const fields: Field[] = [
    {
      name: "type",
      label: "Permit type",
      required: true,
      options: config.permit_types.map((t) => ({
        value: text(t.code),
        label: text(t.label),
      })),
      value: permit?.type || "building",
    },
    {
      name: "applicant_id",
      label: "Applicant",
      required: true,
      options: applicants.map((a) => ({ value: a.id, label: text(a.name) })),
      value: permit?.applicant_id || applicants[0]?.id,
    },
    {
      name: "work_address",
      label: "Work-site address",
      required: true,
      wide: true,
      value: permit?.work_address,
    },
    {
      name: "description",
      label: "Description of proposed work",
      type: "textarea",
      required: true,
      wide: true,
      value: permit?.description,
    },
    {
      name: "contractor_id",
      label: "Contractor (optional)",
      options: contractors.map((c) => ({ value: c.id, label: text(c.name) })),
      value: permit?.contractor_id ?? "",
    },
    {
      name: "area_sqft",
      label: "Work area (square feet)",
      type: "number",
      min: 0,
      max: 1000000,
      step: "1",
      required: true,
      value: permit?.area_sqft ?? 0,
      help: "Active matching fee schedules take precedence. Demo fallback: building $150 + $0.25/sq ft; electrical $75; plumbing $90. Other types require a configured schedule.",
    },
    {
      name: "use_group",
      label: "Use group (optional)",
      value: String(permit?.use_group ?? ""),
      help: "Must match the schedule use group exactly; leave blank for the default schedule.",
    },
    {
      name: "prior_approval",
      label: "Prior approvals have been obtained",
      type: "checkbox",
      value: Boolean(permit?.prior_approval),
      wide: true,
      help: "Required before submitting the application. This is a demonstration rule.",
    },
  ];
  return (
    <Modal
      title={permit ? `Edit ${permit.number}` : "New permit application"}
      onClose={onClose}
    >
      <ErrorBox message={error} />
      {!loaded ? (
        <Loading />
      ) : (
        <Form
          fields={fields}
          submitLabel={permit ? "Save permit" : "Create draft permit"}
          onCancel={onClose}
          onSubmit={async (v) => {
            const p = await api<Permit>(
              permit ? `/permits/${permit.id}` : "/permits",
              permit ? "PATCH" : "POST",
              {
                ...v,
                applicant_id: Number(v.applicant_id),
                contractor_id: v.contractor_id ? Number(v.contractor_id) : null,
                area_sqft: Number(v.area_sqft),
              },
            );
            onSaved(p.id);
          }}
        />
      )}
    </Modal>
  );
}
function PermitDetail({
  id,
  user,
  config,
  onClose,
  changed,
}: {
  id: number;
  user: User;
  config: Config;
  onClose: () => void;
  changed: (s?: string) => void;
}) {
  const [permit, setPermit] = useState<Permit | null>(null),
    [error, setError] = useState(""),
    [tick, setTick] = useState(0),
    [tab, setTab] = useState("Overview"),
    [action, setAction] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Permit>(`/permits/${id}`)
      .then(setPermit)
      .catch((e) => setError(e.message));
  }, [id, tick]);
  function updated(message = "Permit updated") {
    setAction("");
    setTick((x) => x + 1);
    changed(message);
  }
  async function mutate(
    path: string,
    body: unknown,
    message: string,
    method = "POST",
  ) {
    setError("");
    setBusy(true);
    try {
      await api(path, method, body);
      updated(message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (action === "edit" && permit)
    return (
      <PermitForm
        permit={permit}
        config={config}
        onClose={() => setAction("")}
        onSaved={() => updated("Permit changes saved")}
      />
    );
  const canManage = isRole(user, "admin", "clerk"),
    canReview = isRole(user, "admin", "reviewer"),
    canSchedule = canManage,
    canPay = isRole(user, "admin", "clerk", "applicant");
  const statusConfig = config.statuses.find((s) => s.code === permit?.status);
  let nextStatuses: string[] = [];
  try {
    nextStatuses = Array.isArray(statusConfig?.next_statuses)
      ? statusConfig.next_statuses
      : JSON.parse(String(statusConfig?.next_statuses || "[]"));
  } catch {
    /* malformed configuration shows no transitions */
  }
  if (user.role === "applicant")
    nextStatuses =
      permit?.status === "draft"
        ? nextStatuses.filter((s) => s === "submitted")
        : [];
  else if (user.role === "reviewer")
    nextStatuses = nextStatuses.filter((s) =>
      ["under_review", "approved"].includes(s),
    );
  else if (!canManage) nextStatuses = [];
  const paymentKey = `permitsnj-payment-${user.id}-${id}`;
  function getPaymentKey(amountCents: number, simulateFailure: boolean) {
    // Preserve every uncertain attempt by payload: retries reuse the same key,
    // while a deliberately changed amount/decline selection starts a new attempt.
    const fingerprint = `${paymentKey}:${amountCents}:${simulateFailure}`;
    let key = sessionStorage.getItem(fingerprint);
    if (!key) {
      key = crypto.randomUUID();
      sessionStorage.setItem(fingerprint, key);
    }
    return { key, fingerprint };
  }
  const actionFields: Record<string, Field[]> = {
    payment: [
      {
        name: "amount",
        label: "Mock payment amount ($)",
        type: "number",
        min: 0.01,
        max: (permit?.balance_cents || 0) / 100,
        step: "0.01",
        required: true,
        value: (permit?.balance_cents || 0) / 100,
        help: "No card information is collected. This records a simulated payment only.",
      },
      {
        name: "simulate_failure",
        label: "Simulate a provider decline",
        type: "checkbox",
      },
    ],
    review: [
      {
        name: "result",
        label: "Review decision",
        required: true,
        options: [
          { value: "approved", label: "Approved" },
          { value: "changes_requested", label: "Changes requested" },
        ],
      },
      {
        name: "notes",
        label: "Review notes",
        type: "textarea",
        required: true,
        wide: true,
      },
    ],
    inspection: [
      {
        name: "inspector_id",
        label: "Assigned inspector",
        required: true,
        options: config.users
          .filter((u) => u.role === "inspector")
          .map((u) => ({ value: u.id, label: u.name })),
      },
      {
        name: "scheduled_date",
        label: "Inspection date",
        type: "date",
        required: true,
      },
    ],
    notice: [
      {
        name: "kind",
        label: "Document type",
        required: true,
        options: [
          { value: "notice", label: "Notice" },
          { value: "order", label: "Order" },
        ],
      },
      {
        name: "deadline",
        label: "Compliance deadline",
        type: "date",
        required: true,
      },
      {
        name: "description",
        label: "Description and required action",
        type: "textarea",
        required: true,
        wide: true,
      },
    ],
    exemption: [
      {
        name: "exempt",
        label: "Exempt this permit from fees",
        type: "checkbox",
        value: Boolean(permit?.exempt),
      },
      {
        name: "reason",
        label: "Exemption reason",
        type: "textarea",
        required: true,
        value: permit?.exemption_reason || "",
        wide: true,
        help: "Staff must provide a reason. Existing payments can prevent fee changes.",
      },
    ],
    transfer: [
      {
        name: "municipality_id",
        label: "Destination municipality",
        required: true,
        options: config.municipalities
          .filter((m) => m.id !== user.municipality_id)
          .map((m) => ({ value: m.id, label: text(m.name) })),
      },
      {
        name: "applicant_id",
        label: "Destination applicant record ID",
        type: "number",
        min: 1,
        required: true,
        help: "Obtain this ID from the destination administrator. The server verifies municipality membership.",
      },
      {
        name: "contractor_id",
        label: "Destination contractor ID (optional)",
        type: "number",
        min: 1,
      },
    ],
  };
  return (
    <Modal title={permit ? permit.number : "Permit details"} onClose={onClose}>
      <div className="modal-body">
        <ErrorBox message={error} />
        {!permit ? (
          <Loading />
        ) : (
          <>
            <div className="detail-heading">
              <div>
                <span className="eyebrow">{human(permit.type)} PERMIT</span>
                <h2>{permit.work_address}</h2>
                <p>
                  {permit.municipality_name} · {permit.applicant_name}
                </p>
              </div>
              <Badge value={permit.status} />
            </div>
            <div className="progress-track">
              {[
                "draft",
                "submitted",
                "under_review",
                "approved",
                "issued",
                "closed",
              ].map((s, i) => {
                const current = [
                  "draft",
                  "submitted",
                  "under_review",
                  "approved",
                  "issued",
                  "closed",
                ].indexOf(permit.status);
                return (
                  <div
                    className={`progress-step ${i <= current ? "completed" : ""}`}
                    key={s}
                  >
                    <span className="step-dot">
                      {i < current ? <Check size={12} /> : i + 1}
                    </span>
                    <small>{human(s)}</small>
                  </div>
                );
              })}
            </div>
            <div className="tabs" role="tablist" aria-label="Permit sections">
              {[
                "Overview",
                "Payments",
                "Reviews",
                "Inspections",
                "Documents",
                "History",
              ].map((t) => (
                <button
                  key={t}
                  role="tab"
                  aria-selected={tab === t}
                  className={`tab ${tab === t ? "active" : ""}`}
                  onClick={() => setTab(t)}
                >
                  {t}
                </button>
              ))}
            </div>
            {tab === "Overview" && (
              <>
                <div className="detail-grid">
                  <div className="detail-card">
                    <span className="stat-label">Assessed fee</span>
                    <strong className="detail-amount">
                      {money(permit.fee_cents)}
                    </strong>
                    <small>
                      {permit.exempt
                        ? "Fee exemption applied"
                        : permit.assessed_schedule_id
                          ? `Fee schedule #${permit.assessed_schedule_id}`
                          : "Sample demonstration rates"}
                    </small>
                  </div>
                  <div className="detail-card">
                    <span className="stat-label">Paid to date</span>
                    <strong className="detail-amount">
                      {money(permit.paid_cents)}
                    </strong>
                    <small>Mock payments only</small>
                  </div>
                  <div className="detail-card">
                    <span className="stat-label">Remaining balance</span>
                    <strong className="detail-amount">
                      {money(permit.balance_cents)}
                    </strong>
                    <small>
                      {permit.balance_cents
                        ? "Payment outstanding"
                        : "No balance due"}
                    </small>
                  </div>
                </div>
                <div className="detail-description">
                  <h3>Project details</h3>
                  <p>{permit.description}</p>
                  <dl className="detail-meta">
                    <div>
                      <dt>Applicant</dt>
                      <dd>{permit.applicant_name}</dd>
                    </div>
                    <div>
                      <dt>Contractor</dt>
                      <dd>{text(permit.contractor_name)}</dd>
                    </div>
                    <div>
                      <dt>Work area</dt>
                      <dd>{permit.area_sqft} sq ft</dd>
                    </div>
                    <div>
                      <dt>Prior approval</dt>
                      <dd>
                        {permit.prior_approval
                          ? "Confirmed"
                          : "Not yet confirmed"}
                      </dd>
                    </div>
                    <div>
                      <dt>Created</dt>
                      <dd>{date(permit.created_at)}</dd>
                    </div>
                    <div>
                      <dt>Updated</dt>
                      <dd>{date(permit.updated_at)}</dd>
                    </div>
                  </dl>
                </div>
                <div className="form-actions">
                  {((canManage &&
                    ["draft", "submitted", "under_review"].includes(
                      permit.status,
                    )) ||
                    (user.role === "applicant" &&
                      permit.status === "draft")) && (
                    <button
                      className="button secondary small"
                      onClick={() => setAction("edit")}
                    >
                      Edit application
                    </button>
                  )}
                  {canManage && (
                    <button
                      className="button secondary small"
                      onClick={() => setAction("exemption")}
                    >
                      Fee exemption
                    </button>
                  )}
                  {user.role === "admin" && (
                    <button
                      className="button secondary small"
                      onClick={() => setAction("transfer")}
                    >
                      Transfer municipality
                    </button>
                  )}
                  {nextStatuses.map((s) => (
                    <button
                      className="button primary small"
                      disabled={busy}
                      key={s}
                      onClick={() => setAction(`status:${s}`)}
                    >
                      Move to {human(s)}
                      <ArrowRight size={15} />
                    </button>
                  ))}
                </div>
              </>
            )}
            {tab === "Payments" && (
              <>
                <div className="section-heading">
                  <div>
                    <h3>Payment history</h3>
                    <p className="help-text">
                      Mock provider · Remaining balance{" "}
                      {money(permit.balance_cents)}
                    </p>
                  </div>
                  {canPay && permit.balance_cents > 0 && (
                    <button
                      className="button primary small"
                      onClick={() => setAction("payment")}
                    >
                      <Plus size={16} />
                      Record mock payment
                    </button>
                  )}
                </div>
                <Records
                  rows={permit.payments || []}
                  fields={[
                    "amount_cents",
                    "reference",
                    "reconciled",
                    "created_at",
                  ]}
                  actions={(row) =>
                    canManage && !row.reconciled ? (
                      <button
                        className="button secondary small"
                        onClick={() => setAction(`reconcile:${row.id}`)}
                      >
                        Reconcile
                      </button>
                    ) : null
                  }
                />
              </>
            )}
            {tab === "Reviews" && (
              <>
                <div className="section-heading">
                  <h3>Plan reviews</h3>
                  {canReview && (
                    <button
                      className="button primary small"
                      onClick={() => setAction("review")}
                    >
                      <Plus size={16} />
                      Add review
                    </button>
                  )}
                </div>
                <Records
                  rows={permit.plan_reviews || []}
                  fields={["result", "notes", "created_at"]}
                />
              </>
            )}
            {tab === "Inspections" && (
              <>
                <div className="section-heading">
                  <h3>Inspection schedule & results</h3>
                  {canSchedule && (
                    <button
                      className="button primary small"
                      onClick={() => setAction("inspection")}
                    >
                      <Plus size={16} />
                      Schedule inspection
                    </button>
                  )}
                </div>
                <Records
                  rows={permit.inspections || []}
                  fields={[
                    "scheduled_date",
                    "status",
                    "result",
                    "notes",
                    "follow_up",
                  ]}
                  actions={(row) =>
                    (user.role === "admin" ||
                      (user.role === "inspector" &&
                        Number(row.inspector_id) === user.id)) &&
                    !row.result ? (
                      <button
                        className="button secondary small"
                        onClick={() => setAction(`result:${row.id}`)}
                      >
                        Record result
                      </button>
                    ) : null
                  }
                />
              </>
            )}
            {tab === "Documents" && (
              <>
                <div className="section-heading">
                  <h3>Certificates</h3>
                  {canManage && (
                    <button
                      className="button secondary small"
                      onClick={() => setAction("certificate")}
                    >
                      <FileBadge size={16} />
                      Generate certificate
                    </button>
                  )}
                </div>
                <Records
                  rows={permit.certificates || []}
                  fields={["number", "status", "created_at"]}
                  actions={(row) => (
                    <>
                      <a
                        className="button ghost small"
                        href={`/api/certificates/${row.id}/document`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Printer size={15} />
                        View / print
                      </a>
                      {canManage && row.status === "active" && (
                        <button
                          className="button danger small"
                          onClick={() => setAction(`revoke:${row.id}`)}
                        >
                          Revoke
                        </button>
                      )}
                    </>
                  )}
                />
                <div className="section-heading">
                  <h3>Notices & orders</h3>
                  {canManage && (
                    <button
                      className="button secondary small"
                      onClick={() => setAction("notice")}
                    >
                      <Plus size={16} />
                      Create notice
                    </button>
                  )}
                </div>
                <Records
                  rows={permit.notices || []}
                  fields={["kind", "description", "deadline", "status"]}
                  actions={(row) => (
                    <>
                      <a
                        className="button ghost small"
                        href={`/api/notices/${row.id}/document`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <Printer size={15} />
                        View / print
                      </a>
                      {canManage && row.status === "open" && (
                        <button
                          className="button secondary small"
                          onClick={() => setAction(`resolve:${row.id}`)}
                        >
                          Resolve
                        </button>
                      )}
                    </>
                  )}
                />
              </>
            )}
            {tab === "History" && (
              <>
                <h3>Audit history</h3>
                <p className="help-text">
                  Important record and financial changes, retained with their
                  actor and time.
                </p>
                <Records
                  rows={permit.audit || []}
                  fields={["action", "details", "created_at"]}
                />
              </>
            )}
          </>
        )}
      </div>
      {action && action !== "edit" && permit && (
        <Modal
          title={
            action.startsWith("status:")
              ? `Move permit to ${human(action.split(":")[1])}?`
              : action.startsWith("result:")
                ? "Record inspection result"
                : human(action.split(":")[0])
          }
          onClose={() => setAction("")}
        >
          {actionFields[action] ? (
            <Form
              fields={actionFields[action]}
              submitLabel={
                action === "payment"
                  ? "Submit mock payment"
                  : action === "transfer"
                    ? "Confirm transfer"
                    : "Save record"
              }
              onCancel={() => setAction("")}
              onSubmit={async (v) => {
                if (action === "payment") {
                  const amountCents = Math.round(Number(v.amount) * 100);
                  const attempt = getPaymentKey(
                    amountCents,
                    Boolean(v.simulate_failure),
                  );
                  await api(`/permits/${id}/payments`, "POST", {
                    amount_cents: amountCents,
                    simulate_failure: v.simulate_failure,
                    idempotency_key: attempt.key,
                  });
                  sessionStorage.removeItem(attempt.fingerprint);
                } else if (action === "review")
                  await api(`/permits/${id}/plan-reviews`, "POST", v);
                else if (action === "inspection")
                  await api(`/permits/${id}/inspections`, "POST", {
                    ...v,
                    inspector_id: Number(v.inspector_id),
                  });
                else if (action === "notice")
                  await api(`/permits/${id}/notices`, "POST", v);
                else if (action === "exemption")
                  await api(`/permits/${id}/exemption`, "POST", v);
                else if (action === "transfer")
                  await api(`/permits/${id}/transfer`, "POST", {
                    ...v,
                    municipality_id: Number(v.municipality_id),
                    applicant_id: Number(v.applicant_id),
                    contractor_id: v.contractor_id
                      ? Number(v.contractor_id)
                      : null,
                  });
                if (action === "transfer") {
                  changed("Permit transferred to destination municipality");
                  onClose();
                  return;
                }
                updated(
                  action === "payment"
                    ? "Mock payment recorded"
                    : "Record saved",
                );
              }}
            />
          ) : action.startsWith("result:") ? (
            <Form
              fields={[
                {
                  name: "result",
                  label: "Inspection result",
                  required: true,
                  options: [
                    { value: "passed", label: "Passed" },
                    { value: "failed", label: "Failed" },
                  ],
                },
                {
                  name: "notes",
                  label: "Inspector notes",
                  type: "textarea",
                  required: true,
                },
                {
                  name: "follow_up",
                  label: "Follow-up action (optional)",
                  type: "textarea",
                },
              ]}
              onCancel={() => setAction("")}
              onSubmit={async (v) => {
                await api(`/inspections/${action.split(":")[1]}`, "PATCH", v);
                updated("Inspection result recorded");
              }}
            />
          ) : (
            <>
              <div className="modal-body">
                <p>
                  {action === "certificate"
                    ? "Generate a demonstration certificate? The permit must be issued or closed, fully paid, and have a passed inspection."
                    : action.startsWith("revoke:")
                      ? "Revoke this certificate? The record and its history will be retained."
                      : action.startsWith("resolve:")
                        ? "Mark this notice as resolved?"
                        : action.startsWith("reconcile:")
                          ? "Confirm this mock payment has been reconciled? This action is recorded in the audit history."
                          : "Confirm this permit status change. Required approvals and prerequisites will be checked by the server."}
                </p>
                <ErrorBox message={error} />
              </div>
              <div className="modal-footer">
                <button
                  className="button secondary"
                  onClick={() => setAction("")}
                >
                  Cancel
                </button>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => {
                    if (action === "certificate")
                      void mutate(
                        `/permits/${id}/certificates`,
                        {},
                        "Certificate generated",
                      );
                    else if (action.startsWith("status:"))
                      void mutate(
                        `/permits/${id}/status`,
                        { status: action.split(":")[1] },
                        "Permit status updated",
                      );
                    else if (action.startsWith("revoke:"))
                      void mutate(
                        `/certificates/${action.split(":")[1]}/revoke`,
                        {},
                        "Certificate revoked",
                      );
                    else if (action.startsWith("resolve:"))
                      void mutate(
                        `/notices/${action.split(":")[1]}`,
                        { status: "resolved" },
                        "Notice resolved",
                        "PATCH",
                      );
                    else if (action.startsWith("reconcile:"))
                      void mutate(
                        `/payments/${action.split(":")[1]}/reconcile`,
                        {},
                        "Payment reconciled",
                      );
                  }}
                >
                  {busy ? "Saving…" : "Confirm"}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </Modal>
  );
}
function Records({
  rows,
  fields,
  actions,
}: {
  rows: Row[];
  fields: string[];
  actions?: (r: Row) => ReactNode;
}) {
  return !rows.length ? (
    <Empty message="No records have been added to this section." />
  ) : (
    <div className="record-list">
      {rows.map((row) => (
        <div key={row.id} className="record-row">
          <div>
            {fields.map((f) => (
              <div className="record-field" key={f}>
                <span>{human(f)}</span>
                {["status", "result"].includes(f) ? (
                  <Badge value={row[f]} />
                ) : (
                  <strong>
                    {f.endsWith("_cents")
                      ? money(row[f])
                      : f.endsWith("_at") ||
                          f === "scheduled_date" ||
                          f === "deadline"
                        ? date(row[f])
                        : f === "reconciled"
                          ? row[f]
                            ? "Yes"
                            : "No"
                          : text(row[f])}
                  </strong>
                )}
              </div>
            ))}
          </div>
          {actions && <div className="form-actions">{actions(row)}</div>}
        </div>
      ))}
    </div>
  );
}
function Directory({
  page,
  user,
  refresh,
  changed,
}: {
  page: string;
  user: User;
  refresh: number;
  changed: (s?: string) => void;
}) {
  const endpoint = `/${page.toLowerCase()}`;
  const [rows, setRows] = useState<Row[] | null>(null),
    [error, setError] = useState(""),
    [q, setQ] = useState(""),
    [sort, setSort] = useState("name"),
    [current, setCurrent] = useState(1),
    [show, setShow] = useState(false);
  useEffect(() => {
    setRows(null);
    api<Row[]>(endpoint)
      .then(setRows)
      .catch((e) => setError(e.message));
    setCurrent(1);
  }, [endpoint, refresh]);
  const filtered = (rows || [])
      .filter((r) => JSON.stringify(r).toLowerCase().includes(q.toLowerCase()))
      .sort((a, b) => text(a[sort]).localeCompare(text(b[sort]))),
    fields =
      page === "Applicants"
        ? ["name", "email", "phone"]
        : page === "Contractors"
          ? ["name", "license_number", "email"]
          : ["name"];
  return (
    <>
      <Heading
        title={page}
        subtitle={
          page === "Municipalities"
            ? "Municipalities in this demonstration environment."
            : `Maintain your municipality’s ${page.toLowerCase()} directory.`
        }
      >
        {page !== "Municipalities" && isRole(user, "admin", "clerk") && (
          <button className="button primary" onClick={() => setShow(true)}>
            <Plus size={17} />
            New {page.slice(0, -1).toLowerCase()}
          </button>
        )}
      </Heading>
      <section className="panel">
        <div className="table-toolbar">
          <div className="search-field">
            <Search size={18} />
            <input
              aria-label={`Search ${page}`}
              placeholder={`Search ${page.toLowerCase()}…`}
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setCurrent(1);
              }}
            />
          </div>
          <select
            aria-label="Sort directory"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            {fields.map((f) => (
              <option key={f} value={f}>
                Sort by {human(f)}
              </option>
            ))}
          </select>
        </div>
        <ErrorBox message={error} />
        {!rows ? (
          <Loading />
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {fields.map((f) => (
                      <th key={f}>{human(f)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice((current - 1) * 10, current * 10).map((r) => (
                    <tr key={r.id}>
                      {fields.map((f) => (
                        <td key={f}>
                          {f === "name" ? (
                            <strong>{text(r[f])}</strong>
                          ) : (
                            text(r[f])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!filtered.length && <Empty />}
            </div>
            <div className="pagination">
              <span>{filtered.length} records</span>
              <div>
                <button
                  className="icon-button"
                  aria-label="Previous page"
                  disabled={current === 1}
                  onClick={() => setCurrent(current - 1)}
                >
                  <ChevronLeft size={18} />
                </button>
                <span>Page {current}</span>
                <button
                  className="icon-button"
                  aria-label="Next page"
                  disabled={current * 10 >= filtered.length}
                  onClick={() => setCurrent(current + 1)}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>
      {show && (
        <Modal
          title={`New ${page.slice(0, -1).toLowerCase()}`}
          onClose={() => setShow(false)}
        >
          <Form
            fields={fields.map((f) => ({
              name: f,
              label: human(f),
              required: f === "name" || f === "email" || f === "license_number",
              type: f === "email" ? "email" : "text",
            }))}
            onCancel={() => setShow(false)}
            onSubmit={async (v) => {
              await api(endpoint, "POST", v);
              setShow(false);
              changed("Directory record created");
            }}
          />
        </Modal>
      )}
    </>
  );
}
function WorkflowList({
  page,
  user,
  refresh,
  onPermit,
  changed,
}: {
  page: string;
  user: User;
  refresh: number;
  onPermit: (id: number) => void;
  changed: (s?: string) => void;
}) {
  const map: Record<
    string,
    { endpoint: string; fields: string[]; description: string }
  > = {
    Payments: {
      endpoint: "payments",
      fields: [
        "permit_number",
        "work_address",
        "amount_cents",
        "reference",
        "reconciled",
        "created_at",
      ],
      description: "Track mock payments, receipts, and reconciliation.",
    },
    "Plan Reviews": {
      endpoint: "plan-reviews",
      fields: [
        "permit_number",
        "work_address",
        "result",
        "notes",
        "created_at",
      ],
      description:
        "Review decisions and project feedback, connected to each permit.",
    },
    Inspections: {
      endpoint: "inspections",
      fields: [
        "permit_number",
        "work_address",
        "scheduled_date",
        "status",
        "result",
        "follow_up",
      ],
      description:
        "Coordinate scheduled inspections and track follow-up actions.",
    },
    Certificates: {
      endpoint: "certificates",
      fields: [
        "permit_number",
        "number",
        "work_address",
        "status",
        "created_at",
      ],
      description: "Generate, view, and manage demonstration certificates.",
    },
    "Notices & Orders": {
      endpoint: "notices",
      fields: [
        "permit_number",
        "work_address",
        "kind",
        "description",
        "deadline",
        "status",
      ],
      description: "Keep required actions, deadlines, and resolution in view.",
    },
  };
  const spec = map[page];
  const [rows, setRows] = useState<Row[] | null>(null),
    [error, setError] = useState(""),
    [q, setQ] = useState(""),
    [filter, setFilter] = useState(""),
    [sort, setSort] = useState("created_at"),
    [current, setCurrent] = useState(1),
    [reconcile, setReconcile] = useState<number | null>(null),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setRows(null);
    setFilter("");
    setCurrent(1);
    setSort(spec.fields.includes("created_at") ? "created_at" : spec.fields[0]);
    setQ("");
    setError("");
    api<Row[]>(`/${spec.endpoint}`)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [spec.endpoint, refresh]);
  const statusField = spec.fields.includes("status")
    ? "status"
    : spec.fields.includes("result")
      ? "result"
      : spec.fields.includes("reconciled")
        ? "reconciled"
        : "";
  const filtered = (rows || [])
    .filter(
      (r) =>
        JSON.stringify(r).toLowerCase().includes(q.toLowerCase()) &&
        (!filter || text(r[statusField]) === filter),
    )
    .sort((a, b) => text(b[sort]).localeCompare(text(a[sort])));
  return (
    <>
      <Heading title={page} subtitle={spec.description}>
        <button className="button secondary" onClick={() => window.print()}>
          <Printer size={17} />
          Print list
        </button>
      </Heading>
      {page === "Payments" && (
        <div className="banner">
          <CreditCard size={21} />
          <span>
            <strong>Mock payment provider.</strong> These are simulated
            transactions. No card numbers are collected or stored.
          </span>
        </div>
      )}
      <section className="panel">
        <div className="table-toolbar">
          <div className="search-field">
            <Search size={18} />
            <input
              aria-label={`Search ${page}`}
              placeholder={`Search ${page.toLowerCase()}…`}
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setCurrent(1);
              }}
            />
          </div>
          <div className="filters">
            {statusField && (
              <select
                aria-label="Filter records"
                value={filter}
                onChange={(e) => {
                  setFilter(e.target.value);
                  setCurrent(1);
                }}
              >
                <option value="">
                  All{" "}
                  {statusField === "reconciled"
                    ? "reconciliation states"
                    : "statuses"}
                </option>
                {[
                  ...new Set((rows || []).map((r) => text(r[statusField]))),
                ].map((v) => (
                  <option key={v} value={v}>
                    {statusField === "reconciled"
                      ? v === "1"
                        ? "Reconciled"
                        : "Unreconciled"
                      : human(v)}
                  </option>
                ))}
              </select>
            )}
            <select
              aria-label="Sort records"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              {spec.fields.map((f) => (
                <option key={f} value={f}>
                  Sort by {human(f)}
                </option>
              ))}
            </select>
          </div>
        </div>
        <ErrorBox message={error} />
        {!rows ? (
          <Loading />
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    {spec.fields.map((f) => (
                      <th key={f}>{human(f.replace("_cents", ""))}</th>
                    ))}
                    <th>ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice((current - 1) * 10, current * 10).map((r) => (
                    <tr key={r.id}>
                      {spec.fields.map((f) => (
                        <td key={f}>
                          {f === "permit_number" ? (
                            <button
                              className="table-link"
                              onClick={() => onPermit(Number(r.permit_id))}
                            >
                              {text(r[f])}
                            </button>
                          ) : f === "status" || f === "result" ? (
                            <Badge value={r[f]} />
                          ) : f.endsWith("_cents") ? (
                            money(r[f])
                          ) : f === "reconciled" ? (
                            <Badge value={r[f] ? "reconciled" : "pending"} />
                          ) : f.endsWith("_at") ||
                            f === "scheduled_date" ||
                            f === "deadline" ? (
                            date(r[f])
                          ) : (
                            text(r[f])
                          )}
                        </td>
                      ))}
                      <td>
                        <div className="form-actions">
                          <button
                            className="button ghost small"
                            onClick={() => onPermit(Number(r.permit_id))}
                          >
                            Open permit
                            <ArrowUpRight size={14} />
                          </button>
                          {["certificates", "notices"].includes(
                            spec.endpoint,
                          ) && (
                            <a
                              className="icon-button"
                              aria-label="View printable document"
                              href={`/api/${spec.endpoint}/${r.id}/document`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <Printer size={16} />
                            </a>
                          )}
                          {page === "Payments" &&
                            isRole(user, "admin", "clerk") &&
                            !r.reconciled && (
                              <button
                                className="button secondary small"
                                onClick={() => setReconcile(r.id)}
                              >
                                Reconcile
                              </button>
                            )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!filtered.length && (
                <Empty message="Add records through an individual permit’s detail view." />
              )}
            </div>
            <div className="pagination">
              <span>
                {filtered.length} records · Open a permit to manage this
                workflow
              </span>
              <div>
                <button
                  className="icon-button"
                  aria-label="Previous page"
                  disabled={current === 1}
                  onClick={() => setCurrent(current - 1)}
                >
                  <ChevronLeft size={18} />
                </button>
                <span>Page {current}</span>
                <button
                  className="icon-button"
                  aria-label="Next page"
                  disabled={current * 10 >= filtered.length}
                  onClick={() => setCurrent(current + 1)}
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          </>
        )}
      </section>
      {reconcile !== null && (
        <Modal
          title="Reconcile mock payment?"
          onClose={() => setReconcile(null)}
        >
          <div className="modal-body">
            <p>
              Confirm that this simulated payment has been reconciled. A record
              will be added to its audit history.
            </p>
            <ErrorBox message={error} />
          </div>
          <div className="modal-footer">
            <button
              className="button secondary"
              onClick={() => setReconcile(null)}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api(`/payments/${reconcile}/reconcile`, "POST", {});
                  setReconcile(null);
                  changed("Mock payment reconciled");
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Confirm reconciliation
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
function Reports({ config }: { config: Config }) {
  const [from, setFrom] = useState(""),
    [to, setTo] = useState(""),
    [municipality, setMunicipality] = useState(""),
    [data, setData] = useState<{
      summary: {
        permit_count: number;
        assessed_cents: number;
        paid_cents: number;
        balance_cents: number;
      };
      items: Permit[];
    } | null>(null),
    [error, setError] = useState("");
  const query = new URLSearchParams({
    ...(from ? { date_from: from } : {}),
    ...(to ? { date_to: to } : {}),
    ...(municipality ? { municipality_id: municipality } : {}),
  }).toString();
  useEffect(() => {
    setError("");
    api<typeof data>(`/reports?${query}`)
      .then(setData)
      .catch((e) => {
        setData(null);
        setError(e.message);
      });
  }, [query]);
  return (
    <>
      <Heading
        title="Reports"
        subtitle="A clear view of permit activity and demonstration finances."
      >
        <a className="button secondary" href={`/api/reports/export?${query}`}>
          <Download size={17} />
          Export CSV
        </a>
        <button className="button secondary" onClick={() => window.print()}>
          <Printer size={17} />
          Print
        </button>
      </Heading>
      <section className="panel report-filters">
        <div className="field">
          <label htmlFor="report-from">Created from</label>
          <input
            id="report-from"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="report-to">Created through</label>
          <input
            id="report-to"
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="report-municipality">Municipality</label>
          <select
            id="report-municipality"
            value={municipality}
            onChange={(e) => setMunicipality(e.target.value)}
          >
            <option value="">My municipality</option>
            {config.municipalities.map((m) => (
              <option value={m.id} key={m.id}>
                {text(m.name)}
              </option>
            ))}
          </select>
        </div>
        <button
          className="button ghost"
          onClick={() => {
            setFrom("");
            setTo("");
            setMunicipality("");
          }}
        >
          Reset filters
        </button>
      </section>
      <ErrorBox message={error} />
      {data && (
        <>
          <div className="stats-grid">
            {[
              { label: "Permits", value: data.summary.permit_count },
              {
                label: "Assessed fees",
                value: money(data.summary.assessed_cents),
              },
              { label: "Mock payments", value: money(data.summary.paid_cents) },
              {
                label: "Outstanding balance",
                value: money(data.summary.balance_cents),
              },
            ].map((s) => (
              <div className="stat-card" key={s.label}>
                <div className="stat-label">{s.label}</div>
                <div className="stat-value">{s.value}</div>
                <small className="muted">
                  For the selected permit creation dates
                </small>
              </div>
            ))}
          </div>
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2 className="panel-title">Permit detail report</h2>
                <p className="panel-subtitle">
                  Current totals for matching permits · Mock financial records
                </p>
              </div>
              <span className="badge">{data.items.length} records</span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>PERMIT</th>
                    <th>ADDRESS</th>
                    <th>TYPE</th>
                    <th>STATUS</th>
                    <th>ASSESSED</th>
                    <th>PAID</th>
                    <th>BALANCE</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <strong>{p.number}</strong>
                      </td>
                      <td>{p.work_address}</td>
                      <td>{human(p.type)}</td>
                      <td>
                        <Badge value={p.status} />
                      </td>
                      <td>{money(p.fee_cents)}</td>
                      <td>{money(p.paid_cents)}</td>
                      <td className="amount">{money(p.balance_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.items.length && <Empty />}
            </div>
          </section>
        </>
      )}
    </>
  );
}
