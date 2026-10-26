import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  TriangleAlert,
  ArrowRight,
  X,
  FolderOpen,
  RefreshCw,
} from "lucide-react";
import { text, money, human, date, type User, type Row } from "../api";

export function isRole(user: User, ...roles: string[]) {
  return roles.includes(user.role);
}

export function Badge({ value }: { value: unknown }) {
  return (
    <span
      className={`status ${text(value).toLowerCase().replaceAll(" ", "_")}`}
    >
      {human(value)}
    </span>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return message ? (
    <div className="alert error" role="alert">
      <TriangleAlert size={17} />
      {message}
    </div>
  ) : null;
}

export function Empty({
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

export function Loading() {
  return (
    <div role="status" className="empty-state">
      <RefreshCw className="spin" size={25} />
      <p>Loading your workspace…</p>
    </div>
  );
}

export function Modal({
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

export interface Field {
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

export function Form({
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

export function Heading({
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

export function Records({
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
