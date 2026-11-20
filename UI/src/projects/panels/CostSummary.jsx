import { useEffect, useState } from 'react'
import { api } from '../api'

const czk = (n) => (n == null ? '—' : `${Math.round(Number(n)).toLocaleString('cs-CZ')} Kč`)

export default function CostSummary({ projectId, reloadKey, onError }) {
  const [c, setC] = useState(null)

  useEffect(() => {
    api.projectCosts(projectId).then(setC).catch((e) => onError(e.message))
  }, [projectId, reloadKey, onError])

  if (!c) return null

  const pct = c.budget_pct
  const barClass = pct == null ? '' : pct >= 100 ? 'over' : pct >= 90 ? 'warn' : ''

  return (
    <div className="pj-costs">
      <div className="tiles">
        <div className="tile"><span className="k">Materiál (skutečné ceny)</span><span className="v">{czk(c.material_czk)}</span></div>
        <div className="tile"><span className="k">Práce · {c.labor_hours} h × {czk(c.hourly_rate_czk)}</span><span className="v">{czk(c.labor_czk)}</span></div>
        <div className="tile"><span className="k">Přímé náklady celkem</span><span className="v">{czk(c.total_czk)}</span></div>
        <div className={'tile hl' + (c.over_budget ? ' over' : '')}>
          <span className="k">Rozpočet {c.planned_budget_czk != null && `· ${czk(c.planned_budget_czk)}`}</span>
          <span className="v">{pct == null ? '—' : `${pct} %`}</span>
        </div>
      </div>
      {pct != null && (
        <div className="progress"><i className={barClass} style={{ width: `${Math.min(100, pct)}%` }} /></div>
      )}
    </div>
  )
}
