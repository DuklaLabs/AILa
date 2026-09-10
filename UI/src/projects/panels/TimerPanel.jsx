import { useEffect, useState } from 'react'
import { api, can } from '../api'

function fmt(mins) {
  const m = Math.max(0, Math.round(mins))
  const h = Math.floor(m / 60)
  return h ? `${h} h ${m % 60} min` : `${m} min`
}

// Horní lišta: běžící stopky přihlášeného napříč celou appkou.
export default function RunningTimer({ reloadKey, onChange, onError }) {
  const [running, setRunning] = useState(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    api.runningTimer().then(setRunning).catch(() => {})
  }, [reloadKey])

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 20000)
    return () => clearInterval(t)
  }, [])

  if (!running) return null

  async function stop() {
    try {
      await api.stopTimer(running.id)
      setRunning(null)
      onChange()
    } catch (err) { onError(err.message) }
  }

  const mins = (now - new Date(running.started_at + 'Z')) / 60000
  return (
    <span className="pj-timer">
      ⏱ {fmt(mins)}
      <button className="sm" style={{ padding: '0.1rem 0.45rem' }} onClick={stop}>Stop</button>
    </span>
  )
}

// Sekce v kartě úkolu: stopky pro tento úkol + ruční zápis + výpis záznamů.
export function TaskTime({ taskId, perms, onChanged, onError }) {
  const [entries, setEntries] = useState([])
  const [running, setRunning] = useState(null)
  const [mins, setMins] = useState('')

  const canLog = can(perms, 'projects.time:log')

  const reload = () => {
    api.listTaskTime(taskId).then(setEntries).catch((e) => onError(e.message))
    api.runningTimer().then(setRunning).catch(() => {})
  }
  useEffect(reload, [taskId]) // eslint-disable-line react-hooks/exhaustive-deps

  const runningHere = running && running.task_id === taskId
  const total = entries.reduce((a, e) => a + (e.minutes || 0), 0)

  async function act(fn) {
    try { await fn(); reload(); onChanged() } catch (err) { onError(err.message) }
  }
  const start = () => act(() => api.startTimer(taskId))
  const stop = () => act(() => api.stopTimer(running.id))
  const addManual = (e) => {
    e.preventDefault()
    act(async () => { await api.addManualTime(taskId, Number(mins)); setMins('') })
  }

  return (
    <div>
      <div className="muted" style={{ marginBottom: '0.4rem' }}>
        Změřeno celkem: <strong style={{ color: 'var(--pj-fg)' }}>{fmt(total)}</strong>
      </div>
      {canLog && (
        <div className="row" style={{ gap: '0.4rem' }}>
          {runningHere
            ? <button className="danger" onClick={stop}>■ Zastavit stopky</button>
            : <button onClick={start} disabled={!!running}>▶ Spustit stopky</button>}
          <form onSubmit={addManual} className="row" style={{ gap: '0.3rem' }}>
            <input type="number" min="1" placeholder="min" value={mins}
                   onChange={(e) => setMins(e.target.value)} style={{ width: '76px' }} required />
            <button type="submit">Zapsat ručně</button>
          </form>
        </div>
      )}
      {running && !runningHere && (
        <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.3rem' }}>
          Stopky ti běží na jiném úkolu (#{running.task_id}).
        </p>
      )}
      <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.1rem', fontSize: '0.83rem' }}>
        {entries.slice(0, 12).map((e) => (
          <li key={e.id}>
            {e.minutes != null ? fmt(e.minutes) : 'běží…'}
            <span className="muted"> · {e.source === 'timer' ? 'stopky' : 'ručně'} · {String(e.started_at).slice(0, 16).replace('T', ' ')}</span>
          </li>
        ))}
        {entries.length === 0 && <li className="muted">Zatím žádný záznam.</li>}
      </ul>
    </div>
  )
}
