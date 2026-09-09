// Tenký fetch wrapper nad /api služby Projects. Cookie session -> credentials.

const BASE = '/api'

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
    throw new Error((data && (data.detail || data.message)) || `${res.status} ${res.statusText}`)
  }
  return data
}

const q = (params) => {
  const s = Object.entries(params || {})
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
    .join('&')
  return s ? `?${s}` : ''
}

export const api = {
  me: () => req('GET', '/me'),
  listUsers: (search) => req('GET', `/users${q({ q: search })}`),

  listFolders: () => req('GET', '/folders'),
  listProjects: (folder_id, status) => req('GET', `/projects${q({ folder_id, status })}`),
  getProject: (id) => req('GET', `/projects/${id}`),
  createProject: (body) => req('POST', '/projects', body),
  updateProject: (id, fields) => req('PATCH', `/projects/${id}`, fields),

  listPhaseTasks: (phaseId) => req('GET', `/phases/${phaseId}/tasks`),
  listProjectTasks: (projectId) => req('GET', `/tasks${q({ project_id: projectId })}`),
  getTask: (id) => req('GET', `/tasks/${id}`),
  createTask: (body) => req('POST', '/tasks', body),
  updateTask: (id, fields) => req('PATCH', `/tasks/${id}`, fields),
  deleteTask: (id) => req('DELETE', `/tasks/${id}`),
  setTaskStatus: (id, status) => req('POST', `/tasks/${id}/status`, { status }),
  setTaskAssignee: (id, assignee_user_id) =>
    req('POST', `/tasks/${id}/assignee`, { assignee_user_id }),
  setTaskCollaborators: (id, user_ids) =>
    req('PUT', `/tasks/${id}/collaborators`, { user_ids }),
  addDependency: (id, depends_on_task_id) =>
    req('POST', `/tasks/${id}/dependencies`, { depends_on_task_id }),
  removeDependency: (id, depId) => req('DELETE', `/tasks/${id}/dependencies/${depId}`),

  listTaskTime: (taskId) => req('GET', `/tasks/${taskId}/time`),
  startTimer: (taskId, note) => req('POST', `/tasks/${taskId}/time/start`, { note }),
  addManualTime: (taskId, minutes, note) =>
    req('POST', `/tasks/${taskId}/time/manual`, { minutes, note }),
  stopTimer: (entry_id) => req('POST', '/time/stop', { entry_id }),
  runningTimer: () => req('GET', '/time/running'),

  projectCosts: (id, proto_version) =>
    req('GET', `/projects/${id}/costs${q({ proto_version })}`),

  listProposals: (status = 'pending') => req('GET', `/proposals${q({ status })}`),
  approveProposal: (id, note) => req('POST', `/proposals/${id}/approve`, { note }),
  rejectProposal: (id, note) => req('POST', `/proposals/${id}/reject`, { note }),
}

export function userName(users, id) {
  if (!id) return null
  const u = (users || []).find((x) => x.id === id)
  return u ? u.name : `#${id}`
}

export function initials(name) {
  if (!name) return '?'
  const parts = String(name).replace(/#/g, '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  return (parts[0][0] + (parts[1]?.[0] || '')).toUpperCase()
}

export function isOverdue(due, status) {
  if (!due || status === 'done') return false
  return new Date(due) < new Date(new Date().toDateString())
}

// mirror ailacore.rbac.permission_matches
export function can(perms, needed) {
  if (!perms) return false
  return perms.some(
    (g) => g === '*' || g === needed || (g.endsWith('.*') && needed.startsWith(g.slice(0, -1))),
  )
}

export const STATUSES = [
  ['backlog', 'K řešení'],
  ['in_progress', 'V řešení'],
  ['design_review', 'Interní revize'],
  ['blocked', 'Blokováno'],
  ['done', 'Hotovo'],
]

// barva podle kategorie (složky) projektu – hodnota je CSS custom property
export const FOLDER_LABELS = {
  commercial: 'Komerční prototypy',
  internal_rnd: 'Interní R&D',
  overview: 'Globální přehledy',
}
export function folderColor(kind) {
  return kind && FOLDER_LABELS[kind] ? `var(--cat-${kind})` : 'var(--pj-accent)'
}
export const COST_TYPES = [
  ['components', 'Součástky'],
  ['pcb', 'Výroba desek (PCB)'],
  ['mechanical', 'Mechanika (3D/CNC)'],
  ['tools', 'Nástroje'],
]
export const ORDER_STATUSES = [
  ['cart', 'Košík'],
  ['ordered', 'Odesláno dodavateli'],
  ['in_lab', 'Skladem v laboratoři'],
]
