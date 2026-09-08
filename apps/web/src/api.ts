export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1" + path, init);
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      data.error?.code || "INTERNAL",
      data.error?.message || "Operazione non riuscita. Riprova.",
    );
  return data as T;
}
export function readPreferences(): string[] {
  try {
    const p = JSON.parse(
      localStorage.getItem("spesaradar.preferences") || "null",
    );
    return p?.version === 1 && Array.isArray(p.target_ids)
      ? p.target_ids.filter((x: unknown) => typeof x === "string")
      : [];
  } catch {
    return [];
  }
}
export function savePreferences(ids: string[]) {
  try {
    localStorage.setItem(
      "spesaradar.preferences",
      JSON.stringify({ version: 1, target_ids: ids }),
    );
  } catch {
    /* The app remains usable when browser storage is unavailable. */
  }
}
