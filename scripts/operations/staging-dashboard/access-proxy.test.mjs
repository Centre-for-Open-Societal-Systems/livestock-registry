import assert from "node:assert/strict"
import { createServer } from "node:http"
import { test } from "node:test"
import { createAccessProxy } from "./access-proxy.mjs"

test("legacy dashboard requires an existing registry viewing role on every data path", async () => {
  let outage = false
  let backendCalls = 0
  const backend = createServer((request, response) => {
    backendCalls++
    assert.equal(request.headers.authorization, undefined)
    assert.equal(request.headers.cookie, undefined)
    response.setHeader("Content-Type", "application/json")
    response.end(JSON.stringify({ path: request.url, rows: [{ count: 1 }] }))
  })
  const iam = createServer((request, response) => {
    response.setHeader("Content-Type", "application/json")
    if (outage) return response.writeHead(500).end("{}")
    if (request.url.startsWith("/auth/start_authentication_transaction")) {
      return response.end(JSON.stringify({ redirectUrl: "https://keycloak.example.test/realms/staff/protocol/openid-connect/auth" }))
    }
    if (request.headers.authorization === "Bearer invalid") return response.writeHead(401).end("{}")
    const roles = request.headers.authorization === "Bearer admin-session" ? ["Operations Administrator"] : []
    response.end(JSON.stringify({ client_roles: { "livestock-registry-staff-portal": roles } }))
  })
  const listen = server => new Promise(resolve => server.listen(0, "127.0.0.1", resolve))
  await listen(backend)
  await listen(iam)
  const guard = createAccessProxy({ iamUrl: `http://127.0.0.1:${iam.address().port}`, publicUrl: "https://livestock-dashboard.example.test",
    keycloakOrigin: "https://keycloak.example.test", providerId: "3", clientId: "livestock-registry-staff-portal",
    viewRoles: ["Data Validator", "Data Supervisor", "Data Editor", "Operations Administrator", "Technical Administrator"],
    backendUrl: `http://127.0.0.1:${backend.address().port}` })
  await listen(guard)
  const base = `http://127.0.0.1:${guard.address().port}`
  try {
    const home = await fetch(base, { redirect: "manual" })
    assert.equal(home.status, 302)
    assert.equal(home.headers.get("location"), "https://livestock-dashboard.example.test/api/auth/login")
    for (const path of ["/api/charts?charts=livestockKpis", "/api/maps/regions", "/api/export"]) {
      assert.equal((await fetch(base + path)).status, 401)
      assert.equal((await fetch(base + path, { headers: { Cookie: "X-Access-Token=invalid" } })).status, 401)
      assert.equal((await fetch(base + path, { headers: { Cookie: "X-Access-Token=unprivileged" } })).status, 403)
    }
    assert.equal(backendCalls, 0)
    const response = await fetch(base + "/api/charts?charts=livestockKpis", { headers: { Cookie: "X-Access-Token=admin-session; unrelated=private", Authorization: "Bearer should-not-reach-backend" } })
    assert.equal(response.status, 200)
    assert.deepEqual(await response.json(), { path: "/api/charts?charts=livestockKpis", rows: [{ count: 1 }] })
    assert.equal(backendCalls, 1)
    assert.equal((await fetch(base + "/api/health")).status, 200)
    const login = await fetch(base + "/api/auth/login", { redirect: "manual" })
    assert.equal(login.status, 302)
    assert.equal(new URL(login.headers.get("location")).origin, "https://keycloak.example.test")
    outage = true
    assert.equal((await fetch(base + "/api/charts", { headers: { Cookie: "X-Access-Token=admin-session" } })).status, 503)
    assert.equal(backendCalls, 2)
  } finally { await Promise.all([guard, iam, backend].map(server => new Promise(resolve => server.close(resolve)))) }
})
