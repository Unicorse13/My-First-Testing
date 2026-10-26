import { useEffect, useState } from "react";
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
  ArrowRight,
  ChevronRight,
  ChevronDown,
  Menu,
  LogOut,
  Bell,
  HelpCircle,
  Check,
} from "lucide-react";
import { api, setCSRF, human, type Session, type Config } from "./api";
import { ErrorBox, Loading, Modal } from "./components/ui";
import Login from "./features/Login";
import Dashboard from "./features/Dashboard";
import Permits from "./features/Permits";
import PermitForm from "./features/PermitForm";
import PermitDetail from "./features/PermitDetail";
import Directory from "./features/Directory";
import WorkflowList from "./features/WorkflowList";
import Reports from "./features/Reports";
import Fees from "./Fees";

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
