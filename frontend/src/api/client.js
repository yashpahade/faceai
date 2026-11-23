// Thin fetch wrapper: JWT header, JSON/FormData, consistent errors.
import { useAuth } from "../store/auth";

export class ApiError extends Error {
  constructor(status, detail) {
    const msg =
      typeof detail === "string"
        ? detail
        : detail?.message ||
          (Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : `Request failed (${status})`);
    super(msg);
    this.status = status;
    this.detail = detail;
  }
}

export async function api(path, { method = "GET", json, form, auth = true, raw = false, signal } = {}) {
  const headers = {};
  const token = useAuth.getState().token;
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form; // browser multipart boundary khud lagata hai
  }
  let res;
  try {
    res = await fetch(path, { method, headers, body, signal });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(0, navigator.onLine ? "Server unreachable" : "You are offline");
  }
  if (res.status === 401 && auth && token) {
    useAuth.getState().logout(); // token expire/revoke -> login pe wapas
  }
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    if (res.status === 503 && res.headers.get("Retry-After")) detail = "Server busy, please retry in a moment";
    throw new ApiError(res.status, detail);
  }
  if (raw) return res;
  if (res.status === 204) return null;
  return res.json();
}

export const fd = (entries) => {
  const f = new FormData();
  for (const [k, v] of entries) f.append(k, v);
  return f;
};
