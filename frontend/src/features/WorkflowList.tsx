import { useEffect, useState } from "react";
import {
  CreditCard,
  Search,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Printer,
} from "lucide-react";
import { api, text, money, human, date, type User, type Row } from "../api";
import {
  isRole,
  Badge,
  ErrorBox,
  Empty,
  Loading,
  Modal,
  Heading,
} from "../components/ui";

export default function WorkflowList({
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
