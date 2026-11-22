export async function onRequest({ env }) {
  if (!env.DB) return Response.json({ status: "error", detail: "D1 binding DB is not configured." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  try {
    await env.DB.prepare("SELECT 1 AS ok").first();
    return Response.json({ status: "ok", service: "multi-source-agentic-rag", database_configured: true }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return Response.json({ status: "error", detail: `D1 query failed: ${error.message}` }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
