import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

function norm(s) { return (s || '').toLowerCase().trim() }

function guessByName(hint, list, nameKey = 'name') {
  const h = norm(hint)
  if (!h || !list?.length) return null
  return (
    list.find((x) => norm(x[nameKey]) === h) ||
    list.find((x) => norm(x[nameKey]).includes(h) || h.includes(norm(x[nameKey]))) ||
    null
  )
}

export default function PocketPanel({ users, onClose, onProposed, onError }) {
  const [recordings, setRecordings] = useState([])
  const [loadingList, setLoadingList] = useState(true)
  const [recording, setRecording] = useState(null)
  const [extraction, setExtraction] = useState(null) // { recordingTitle, rows: [...] }
  const [projects, setProjects] = useState([])
  const [phasesByProject, setPhasesByProject] = useState({})
  const [busy, setBusy] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [recTitle, setRecTitle] = useState('')
  const mediaRecRef = useRef(null)
  const chunksRef = useRef([])

  const reloadRecordings = () =>
    api.listPocketRecordings().then((r) => setRecordings(r.data || [])).catch((e) => onError(e.message))

  useEffect(() => {
    setLoadingList(true)
    Promise.all([reloadRecordings(), api.listProjects().then(setProjects).catch(() => [])])
      .finally(() => setLoadingList(false))
    return () => {
      if (mediaRecRef.current && mediaRecRef.current.state !== 'inactive') {
        mediaRecRef.current.stop()
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.start()
      mediaRecRef.current = rec
      setIsRecording(true)
    } catch (e) {
      onError('Mikrofon nedostupný: ' + e.message)
    }
  }

  function stopAndUpload() {
    const rec = mediaRecRef.current
    if (!rec) return
    setIsRecording(false)
    rec.onstop = async () => {
      rec.stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      setBusy(true)
      try {
        await api.uploadPocketRecording(blob, recTitle || undefined)
        setRecTitle('')
        await reloadRecordings()
      } catch (e) { onError(e.message) } finally { setBusy(false) }
    }
    rec.stop()
  }

  async function openRecording(r) {
    setBusy(true)
    setExtraction(null)
    try {
      const full = await api.getPocketRecording(r.id)
      setRecording(full.data)
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }

  async function ensurePhases(projectId) {
    if (!projectId) return []
    if (phasesByProject[projectId]) return phasesByProject[projectId]
    const full = await api.getProject(projectId)
    const phases = full.phases || []
    setPhasesByProject((m) => ({ ...m, [projectId]: phases }))
    return phases
  }

  async function extract() {
    if (!recording) return
    setBusy(true)
    try {
      const res = await api.extractPocketTasks(recording.id)
      const rows = []
      for (const c of res.candidates || []) {
        const project = guessByName(c.project_hint, projects)
        const phases = project ? await ensurePhases(project.id) : []
        const phase = guessByName(c.phase_hint, phases) || phases[0] || null
        const assignee = guessByName(c.assignee_name, users, 'name')
        rows.push({
          title: c.title || '',
          description: c.description || '',
          due_on: c.due_on || '',
          project_id: project?.id || '',
          phase_id: phase?.id || '',
          assignee_user_id: assignee?.id || '',
          skip: false,
        })
      }
      setExtraction({ recordingTitle: res.recording?.title, rows })
      if (!rows.length) onError('LLM v přepisu nenašel žádné konkrétní úkoly.')
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }

  function updateRow(idx, patch) {
    setExtraction((ex) => {
      const rows = [...ex.rows]
      rows[idx] = { ...rows[idx], ...patch }
      return { ...ex, rows }
    })
  }

  async function onRowProjectChange(idx, projectId) {
    const phases = projectId ? await ensurePhases(Number(projectId)) : []
    updateRow(idx, { project_id: projectId, phase_id: phases[0]?.id || '' })
  }

  async function submit() {
    if (!extraction) return
    const tasks = extraction.rows
      .filter((r) => !r.skip && r.title.trim() && r.phase_id)
      .map((r) => ({
        title: r.title.trim(),
        description: r.description || null,
        due_on: r.due_on || null,
        assignee_user_id: r.assignee_user_id || null,
        phase_id: Number(r.phase_id),
      }))
    if (!tasks.length) { onError('Není co navrhnout — každý úkol potřebuje název a projekt/fázi.'); return }
    setBusy(true)
    try {
      await api.proposePocketTasks(recording.id, tasks)
      setExtraction(null)
      onProposed()
    } catch (e) { onError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="pj-modal-scrim" onClick={onClose}>
      <div className="pj-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '720px', width: '95vw' }}>
        <div className="pj-modal-head">
          <div>
            <h2 style={{ margin: 0, fontSize: '1rem' }}>Pocket — nahrávky a úkoly</h2>
            <span className="muted" style={{ fontSize: '0.82rem' }}>
              Nahraj schůzku nebo vyber existující přepis, AI navrhne úkoly ke schválení.
            </span>
          </div>
          <button className="ghost" onClick={onClose}>✕</button>
        </div>
        <div className="pj-modal-body">
          <div className="pj-prop">
            <div className="kind">Nová nahrávka</div>
            <div className="row" style={{ marginTop: '0.5rem', flexWrap: 'wrap' }}>
              <input
                placeholder="Název (nepovinné)"
                value={recTitle}
                onChange={(e) => setRecTitle(e.target.value)}
                disabled={isRecording}
                style={{ flex: 1, minWidth: '160px' }}
              />
              {!isRecording ? (
                <button className="primary" onClick={startRecording} disabled={busy}>● Nahrávat</button>
              ) : (
                <button className="danger" onClick={stopAndUpload}>■ Zastavit a nahrát na Pocket</button>
              )}
            </div>
            {isRecording && <div className="muted" style={{ marginTop: '0.4rem' }}>Nahrávám z mikrofonu…</div>}
          </div>

          <div className="pj-prop">
            <div className="kind">Nahrávky ({recordings.length})</div>
            {loadingList && <div className="empty">Načítám…</div>}
            {!loadingList && recordings.length === 0 && <div className="empty">Zatím žádné nahrávky.</div>}
            <div style={{ maxHeight: '180px', overflowY: 'auto', marginTop: '0.4rem' }}>
              {recordings.map((r) => (
                <div
                  key={r.id}
                  className="row"
                  style={{
                    justifyContent: 'space-between', padding: '0.3rem 0.4rem', cursor: 'pointer',
                    background: recording?.id === r.id ? 'var(--card-bg2)' : 'transparent', borderRadius: '6px',
                  }}
                  onClick={() => openRecording(r)}
                >
                  <span>{r.title || r.id}</span>
                  <span className="muted" style={{ fontSize: '0.78rem' }}>
                    {r.state}{r.recording_at ? ` · ${String(r.recording_at).slice(0, 10)}` : ''}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {recording && (
            <div className="pj-prop">
              <div className="kind">{recording.title || recording.id}</div>
              {recording.state !== 'completed' ? (
                <div className="muted" style={{ marginTop: '0.4rem' }}>
                  Nahrávka ještě není přepsaná (stav: {recording.state}).
                </div>
              ) : !extraction ? (
                <div style={{ marginTop: '0.5rem' }}>
                  <button className="primary" onClick={extract} disabled={busy}>
                    Extrahovat úkoly (AI)
                  </button>
                </div>
              ) : (
                <div style={{ marginTop: '0.5rem' }}>
                  {extraction.rows.map((row, idx) => (
                    <div key={idx} className="pj-prop" style={{ opacity: row.skip ? 0.5 : 1 }}>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <input
                          value={row.title}
                          onChange={(e) => updateRow(idx, { title: e.target.value })}
                          style={{ flex: 1, fontWeight: 700 }}
                        />
                        <label className="muted" style={{ fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                          <input
                            type="checkbox"
                            checked={row.skip}
                            onChange={(e) => updateRow(idx, { skip: e.target.checked })}
                          /> vynechat
                        </label>
                      </div>
                      <textarea
                        rows={2}
                        placeholder="Popis (nepovinné)"
                        value={row.description}
                        onChange={(e) => updateRow(idx, { description: e.target.value })}
                        style={{ width: '100%', marginTop: '0.4rem' }}
                      />
                      <div className="row" style={{ marginTop: '0.4rem', flexWrap: 'wrap' }}>
                        <select
                          value={row.project_id}
                          onChange={(e) => onRowProjectChange(idx, e.target.value)}
                        >
                          <option value="">— projekt —</option>
                          {projects.map((p) => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>
                        <select
                          value={row.phase_id}
                          onChange={(e) => updateRow(idx, { phase_id: e.target.value })}
                          disabled={!row.project_id}
                        >
                          <option value="">— fáze —</option>
                          {(phasesByProject[row.project_id] || []).map((p) => (
                            <option key={p.id} value={p.id}>{p.name}</option>
                          ))}
                        </select>
                        <select
                          value={row.assignee_user_id}
                          onChange={(e) => updateRow(idx, { assignee_user_id: e.target.value })}
                        >
                          <option value="">— řešitel —</option>
                          {users.map((u) => (
                            <option key={u.id} value={u.id}>{u.name}</option>
                          ))}
                        </select>
                        <input
                          type="date"
                          value={row.due_on}
                          onChange={(e) => updateRow(idx, { due_on: e.target.value })}
                        />
                      </div>
                    </div>
                  ))}
                  <div className="row" style={{ marginTop: '0.5rem' }}>
                    <button className="primary" onClick={submit} disabled={busy}>
                      Navrhnout úkoly ke schválení
                    </button>
                    <button className="ghost" onClick={() => setExtraction(null)}>Zrušit</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
