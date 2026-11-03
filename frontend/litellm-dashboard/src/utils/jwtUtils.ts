import { jwtDecode } from "jwt-decode";

export function isJwtExpired(token: string): boolean {
  try {
    const decoded: unknown = jwtDecode(token);
    if (decoded && typeof (decoded as Record<string, unknown>).exp === "number") {
      return ((decoded as Record<string, unknown>).exp as number) * 1000 <= Date.now();
    }
    return false;
  } catch {
    // If we can't decode, treat as invalid/expired
    return true;
  }
}

export function decodeToken(token: string | null): Record<string, unknown> | null {
  if (!token) return null;
  try {
    return jwtDecode(token) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function checkTokenValidity(token: string | null): boolean {
  if (!token) return false;
  const decoded = decodeToken(token);
  return decoded !== null && !isJwtExpired(token);
}
