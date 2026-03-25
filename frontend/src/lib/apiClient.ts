/**
 * API client — thin fetch wrapper for FastAPI backend.
 * In dev, Vite proxies /api to http://localhost:8000.
 * In prod, set VITE_API_URL to the backend URL.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${path} - ${body}`);
  }

  return res.json();
}
