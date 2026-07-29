// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

interface IRequestParams {
  url: string;
  body?: object;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  queryParams?: Record<string, any>;
  headers?: Record<string, string>;
}

const request = async <T>({
  url = '',
  method = 'GET',
  body,
  queryParams = {},
  headers = {
    'content-type': 'application/json',
  },
}: IRequestParams): Promise<T> => {
  const response = await fetch(`${url}?${new URLSearchParams(queryParams).toString()}`, {
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers,
  });

  const responseText = await response.text();

  // PM-0016: a non-2xx response must reject even when it carries a valid JSON
  // body (e.g. a structured `{ error }` payload) — otherwise callers can't tell
  // a real dependency failure from a successful empty/degraded payload.
  //
  // Review round 2: only non-2xx bodies get a lenient parse. An error response
  // isn't guaranteed to be JSON (framework HTML 500 page, or a plain-text body
  // used deliberately for old/new client compatibility during a rolling deploy
  // — see pages/api/product-reviews*), so swallow the parse failure ONLY here
  // and fall back to the raw text / status. A malformed 2xx body is a genuine
  // server bug, not a classified error, and must still throw (JSON.parse below
  // is intentionally NOT wrapped for the success path — that's the original,
  // correct behavior; review round 2 caught an earlier version of this fix that
  // over-broadened the try/catch to also swallow malformed-2xx bodies as
  // "success", which is wrong).
  if (!response.ok) {
    let parsedError: unknown;
    try {
      parsedError = responseText ? JSON.parse(responseText) : undefined;
    } catch {
      parsedError = undefined;
    }
    const message = parsedError && typeof parsedError === 'object' && 'error' in parsedError
      ? String((parsedError as { error: unknown }).error)
      : responseText || `Request failed with status ${response.status}`;
    const error = new Error(message) as Error & { status: number };
    error.status = response.status;
    throw error;
  }

  if (!responseText) return undefined as unknown as T;
  return JSON.parse(responseText) as T;
};

export default request;
