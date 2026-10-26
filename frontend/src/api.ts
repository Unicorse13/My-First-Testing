export interface User {
  id: number;
  name: string;
  email: string;
  role: string;
  municipality_id: number;
}
export interface Session {
  user: User;
  csrf_token: string;
  demo: boolean;
}
export interface Row {
  [key: string]: unknown;
  id: number;
}
export interface Permit extends Row {
  number: string;
  status: string;
  type: string;
  description: string;
  work_address: string;
  fee_cents: number;
  paid_cents: number;
  balance_cents: number;
  applicant_id: number;
  contractor_id: number | null;
  area_sqft: number;
  prior_approval: number;
  exempt: number;
  exemption_reason: string;
  applicant_name: string;
  municipality_name: string;
  created_at: string;
  updated_at: string;
  plan_reviews: Row[];
  payments: Row[];
  inspections: Row[];
  certificates: Row[];
  notices: Row[];
  audit: Row[];
}
export interface Config {
  permit_types: Row[];
  statuses: Row[];
  municipalities: Row[];
  users: User[];
}
let csrf = "";
export function setCSRF(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "The server could not complete this request." }));
    const message =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map(
                (e: { msg: string; loc: string[] }) =>
                  `${e.loc?.slice(1).join(" ")}: ${e.msg}`,
              )
              .join("; ")
          : "Request failed.";
    throw new Error(message);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const text = (value: unknown) =>
  value === null || value === undefined ? "—" : String(value);
export const money = (value: unknown) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number(value || 0) / 100,
  );
export const human = (value: unknown) =>
  text(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
export const date = (value: unknown) =>
  value
    ? new Date(
        String(value).length === 10 ? `${value}T12:00:00` : String(value),
      ).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "—";
