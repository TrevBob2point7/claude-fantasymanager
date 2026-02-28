const BASE_URL = "/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: string | Array<{ msg: string }> })
      .detail;
    let message: string;
    if (Array.isArray(detail)) {
      message = detail.map((d) => d.msg).join(", ");
    } else {
      message = detail ?? `Request failed: ${res.status}`;
    }

    if (res.status === 401) {
      const hadToken = !!token;
      localStorage.removeItem("token");
      if (hadToken) {
        window.location.href = "/login";
      }
      if (path === "/auth/login") {
        throw new Error("Invalid email or password");
      }
    }

    throw new Error(message);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body != null ? JSON.stringify(body) : undefined,
  });
}

export function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}
