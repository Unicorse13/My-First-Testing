import { useEffect, useState } from "react";
import {
  FileText,
  CreditCard,
  ClipboardCheck,
  CalendarCheck,
  Plus,
  ArrowUpRight,
  ArrowRight,
  ChevronRight,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { api, money, human, date, type User, type Permit } from "../api";
import {
  isRole,
  Badge,
  ErrorBox,
  Empty,
  Loading,
  Heading,
} from "../components/ui";

export default function Dashboard({
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
