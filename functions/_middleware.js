// Public demo mode: no login or HTTP Basic Auth is required.
// Keep a same-origin guard for browser-initiated writes to reduce CSRF risk.
export async function onRequest({ request, next }) {
  const method = request.method.toUpperCase();
  if (["GET", "HEAD", "OPTIONS"].includes(method)) return next();

  const requestUrl = new URL(request.url);
  const origin = request.headers.get("Origin");
  const fetchSite = request.headers.get("Sec-Fetch-Site");

  if ((origin && origin !== requestUrl.origin) || fetchSite === "cross-site") {
    return Response.json(
      { detail: "Cross-site requests are not allowed." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  return next();
}
