import { useEffect, useState } from "react";
import { FileBadge, Plus, ArrowRight, Printer, Check } from "lucide-react";
import {
  api,
  text,
  money,
  human,
  date,
  type User,
  type Config,
  type Permit,
} from "../api";
import {
  isRole,
  Badge,
  ErrorBox,
  Loading,
  Modal,
  type Field,
  Form,
  Records,
} from "../components/ui";
import PermitForm from "./PermitForm";

export default function PermitDetail({
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
