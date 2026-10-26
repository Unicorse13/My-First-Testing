import { useEffect, useState } from "react";
import {
  Search,
  Plus,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
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
  Empty,
  Loading,
  Heading,
} from "../components/ui";

export default function Permits({
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
