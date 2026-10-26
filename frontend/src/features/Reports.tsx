import { useEffect, useState } from "react";
import { Download, Printer } from "lucide-react";
import { api, text, money, human, type Config, type Permit } from "../api";
import { Badge, ErrorBox, Empty, Heading } from "../components/ui";

export default function Reports({ config }: { config: Config }) {
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
