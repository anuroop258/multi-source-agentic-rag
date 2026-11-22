const encoder = new TextEncoder();

async function digest(value) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
}

function base64Utf8(value) {
  const bytes = encoder.encode(value);
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function constantTimeEqual(a, b) {
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i += 1) difference |= a[i] ^ b[i];
  return difference === 0;
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const path = new URL(request.url).pathname;
  if (path === "/healthz") return next();

  const username = env.APP_USERNAME || "";
  const password = env.APP_PASSWORD || "";
  if (!username || !password) {
    return new Response(JSON.stringify({ detail: "Cloudflare Pages login is not configured." }), {
      status: 503,
      headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
    });
  }

  // Reject browser-originated cross-site write requests before checking Basic Auth.
  // Basic Auth is a shared personal-demo login, not multi-user session management.
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method.toUpperCase())) {
    const origin = request.headers.get("Origin");
    const fetchSite = request.headers.get("Sec-Fetch-Site");
    if ((origin && origin !== new URL(request.url).origin) || fetchSite === "cross-site") {
      return new Response(JSON.stringify({ detail: "Cross-site requests are not allowed." }), {
        status: 403,
        headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      });
    }
  }

  const authorization = request.headers.get("Authorization") || "";
  const expected = `Basic ${base64Utf8(`${username}:${password}`)}`;
  const [receivedHash, expectedHash] = await Promise.all([digest(authorization), digest(expected)]);
  if (!authorization.startsWith("Basic ") || !constantTimeEqual(receivedHash, expectedHash)) {
    return new Response(JSON.stringify({ detail: "Authentication required." }), {
      status: 401,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        "WWW-Authenticate": 'Basic realm="Multi-Source Agentic RAG"',
      },
    });
  }
  return next();
}
