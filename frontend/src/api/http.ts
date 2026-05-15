export type QueryParams = Record<string, string | number | null | undefined>;

export function buildQueryString(params: QueryParams): string {
  const query = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      query.append(key, String(value));
    }
  }

  return query.toString();
}

export function withQuery(path: string, params: QueryParams): string {
  const query = buildQueryString(params);
  return query ? `${path}?${query}` : path;
}

export async function parseJsonResponse(
  response: Response,
  failureMessage: string,
): Promise<unknown> {
  if (!response.ok) {
    throw new Error(`${failureMessage}: ${response.statusText || response.status}`);
  }

  return await response.json() as unknown;
}
