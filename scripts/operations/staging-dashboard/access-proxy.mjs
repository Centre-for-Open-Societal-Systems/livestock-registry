// Protect the installed legacy dashboard using its registry's existing IAM roles.
import { createServer, request as proxyRequest } from "node:http"
import { realpathSync } from "node:fs"
import { fileURLToPath } from "node:url"

const SESSION_COOKIES = new Set(["X-Access-Token", "X-ID-Token", "X-Session-Id", "X-CSRF-Token"])

export function createAccessProxy({ iamUrl, publicUrl, keycloakOrigin, providerId, clientId, viewRoles, backendUrl }) {
  const publicOrigin = new URL(publicUrl).origin
  const backend = new URL(backendUrl)
  if (backend.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(backend.hostname)) throw new Error("Legacy backend must be pod-local HTTP")
  if (!viewRoles.length) throw new Error("Existing registry viewing roles are required")
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, publicOrigin)
    const json = (status, error) => {
      response.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" })
      response.end(JSON.stringify({ error }))
    }
    const login = () => {
      if (url.pathname.startsWith("/api/")) return json(401, "Not signed in")
      response.writeHead(302, { Location: `${publicOrigin}/api/auth/login`, "Cache-Control": "no-store" })
      response.end()
    }
    try {
      if (url.pathname === "/api/auth/login") {
        const start = new URL(`${iamUrl}/auth/start_authentication_transaction`)
        start.searchParams.set("id", providerId)
        start.searchParams.set("redirect_uri", `${publicOrigin}/`)
        const result = await fetch(start, { method: "POST", headers: { Accept: "application/json" }, signal: AbortSignal.timeout(10000) })
        const data = await result.json()
        if (!result.ok || new URL(data.redirectUrl).origin !== keycloakOrigin) return json(503, "Sign-in service unavailable")
        response.writeHead(302, { Location: data.redirectUrl, "Cache-Control": "no-store" })
        return response.end()
      }
      if (url.pathname !== "/api/health") {
        const cookies = (request.headers.cookie ?? "").split(";").map(item => item.trim()).filter(item => SESSION_COOKIES.has(item.split("=", 1)[0]))
        const access = cookies.find(item => item.startsWith("X-Access-Token="))?.slice("X-Access-Token=".length)
        if (!access) return login()
        const result = await fetch(`${iamUrl}/auth/get_user_profile`, {
          headers: { Authorization: `Bearer ${access}`, Cookie: cookies.join("; "), Accept: "application/json" },
          signal: AbortSignal.timeout(5000),
        })
        if ([401, 403].includes(result.status)) return login()
        if (!result.ok) return json(503, "Sign-in service unavailable")
        const profile = await result.json()
        const roles = profile.client_roles?.[clientId]
        if (!Array.isArray(roles) || !viewRoles.some(role => roles.includes(role))) return json(403, "Registry viewing access is required")
      }
      const headers = { ...request.headers, host: backend.host, "x-forwarded-host": new URL(publicOrigin).host, "x-forwarded-proto": "https" }
      delete headers.authorization
      delete headers.cookie
      const proxied = proxyRequest(new URL(url.pathname + url.search, backend), { method: request.method, headers }, upstream => {
        response.writeHead(upstream.statusCode, { ...upstream.headers, "cache-control": "no-store" })
        upstream.pipe(response)
      })
      proxied.setTimeout(30000, () => proxied.destroy())
      proxied.on("error", () => { if (!response.headersSent) json(503, "Dashboard unavailable"); else response.destroy() })
      request.pipe(proxied)
    } catch { json(503, "Sign-in service unavailable") }
  })
  server.on("upgrade", (request, socket) => socket.end("HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n"))
  return server
}

// ConfigMap mounts are symlinks; Node resolves import.meta.url to their target.
if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const required = name => { if (!process.env[name]) throw new Error(`${name} is required`); return process.env[name] }
  createAccessProxy({ iamUrl: required("LEGACY_IAM_URL"), publicUrl: required("LEGACY_PUBLIC_URL"),
    keycloakOrigin: required("LEGACY_KEYCLOAK_ORIGIN"), providerId: required("LEGACY_PROVIDER_ID"),
    clientId: required("LEGACY_REGISTRY_CLIENT_ID"), viewRoles: JSON.parse(required("LEGACY_VIEW_ROLES")),
    backendUrl: "http://127.0.0.1:3000" }).listen(8080, "0.0.0.0")
}
