import { useEffect, useState } from "react";
import { Search, Plus, ChevronLeft, ChevronRight } from "lucide-react";
import { api, text, human, type User, type Row } from "../api";
import {
  isRole,
  ErrorBox,
  Empty,
  Loading,
  Modal,
  Form,
  Heading,
} from "../components/ui";

export default function Directory({
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
