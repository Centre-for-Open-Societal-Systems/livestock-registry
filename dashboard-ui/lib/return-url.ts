// Resolves where the header's "Back" control should navigate.
//
// The staff portal sends the page it left behind as a ?returnUrl= parameter. That
// value arrives from the query string, so it is only honoured when it points at
// the configured portal — otherwise a crafted link could turn this button into an
// open redirect. NEXT_PUBLIC_PORTAL_URL doubles as the allowed origin and as the
// fallback target when no usable returnUrl was supplied.

const PORTAL_URL = process.env.NEXT_PUBLIC_PORTAL_URL || ''

function portalOrigin(): string | null {
  if (!PORTAL_URL) return null
  try {
    return new URL(PORTAL_URL).origin
  } catch {
    return null
  }
}

/** A candidate is usable when it is a same-app path or lives on the portal's origin. */
function accept(candidate: string): string | null {
  if (!candidate) return null

  // Root-relative paths stay inside this app and cannot change origin. The
  // second character guard rejects protocol-relative "//evil.example" URLs.
  if (candidate.startsWith('/') && !candidate.startsWith('//')) return candidate

  const allowed = portalOrigin()
  if (!allowed) return null

  try {
    const url = new URL(candidate)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null
    return url.origin === allowed ? url.toString() : null
  } catch {
    return null
  }
}

export function resolveReturnUrl(search: string, referrer?: string): string | null {
  const requested = new URLSearchParams(search).get('returnUrl')
  if (requested) {
    const accepted = accept(requested)
    if (accepted) return accepted
  }

  // Reached without a returnUrl — a bookmark, or a portal build that predates the
  // nav patch. The referrer recovers the exact page when it was the portal.
  if (referrer) {
    const accepted = accept(referrer)
    if (accepted) return accepted
  }

  return PORTAL_URL || null
}
