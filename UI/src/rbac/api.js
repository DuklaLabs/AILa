// Tenký fetch wrapper nad /api/rbac. Cookie session -> credentials: 'include'.

const BASE = '/api/rbac'

async function req(method, path, body) {
  const opts = { method, credentials: 'include', headers: {} }
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(body)
  }
  const res = await fetch(BASE + path, opts)
  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Nepřihlášeno')
  }
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const detail = data && (data.detail || data.message)
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return data
}

export const api = {
  effective: () => req('GET', '/effective'),

  listPermissions: () => req('GET', '/permissions'),
  createPermission: (name, description) => req('POST', '/permissions', { name, description }),
  deletePermission: (name, cascade = false) =>
    req('DELETE', `/permissions/${encodeURIComponent(name)}${cascade ? '?cascade=true' : ''}`),

  listRoles: () => req('GET', '/roles'),
  createRole: (name, description) => req('POST', '/roles', { name, description }),
  patchRole: (name, description) => req('PATCH', `/roles/${encodeURIComponent(name)}`, { description }),
  deleteRole: (name) => req('DELETE', `/roles/${encodeURIComponent(name)}`),
  setRolePermissions: (name, permissions) =>
    req('PUT', `/roles/${encodeURIComponent(name)}/permissions`, { permissions }),

  listUsers: (q, limit = 50) =>
    req('GET', `/users?limit=${limit}${q ? `&q=${encodeURIComponent(q)}` : ''}`),
  setUserRoles: (id, primary, secondary) =>
    req('PUT', `/users/${id}/roles`, { primary, secondary }),
  setUserPermissions: (id, permissions) =>
    req('PUT', `/users/${id}/permissions`, { permissions }),

  listAudit: (limit = 100) => req('GET', `/audit?limit=${limit}`),
}
