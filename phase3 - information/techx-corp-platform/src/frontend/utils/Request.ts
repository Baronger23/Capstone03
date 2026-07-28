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
  // PM-0016 review: an error response isn't guaranteed to be JSON (e.g. a
  // framework-level 500/502 can come back as an HTML/text error page). Parsing
  // unconditionally would throw a raw SyntaxError instead of the classified
  // Error below, losing the HTTP status this fix exists to preserve.
  let parsed: unknown;
  try {
    parsed = responseText ? JSON.parse(responseText) : undefined;
  } catch {
    parsed = undefined;
  }

  // PM-0016: a non-2xx response must reject even when it carries a valid JSON
  // body (e.g. a structured `{ error }` payload) — otherwise callers can't tell
  // a real dependency failure from a successful empty/degraded payload.
  if (!response.ok) {
    const message = parsed && typeof parsed === 'object' && 'error' in parsed
      ? String((parsed as { error: unknown }).error)
      : `Request failed with status ${response.status}`;
    const error = new Error(message) as Error & { status: number };
    error.status = response.status;
    throw error;
  }

  return parsed as T;
};

export default request;
