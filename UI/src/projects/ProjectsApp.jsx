import { useCallback, useEffect, useState } from 'react'
import { api, can, folderColor } from './api'
import ProjectTree from './panels/ProjectTree'
import BoardView from './panels/BoardView'
import TaskDrawer from './panels/TaskDrawer'
import CostSummary from './panels/CostSummary'
import ProposalsPanel from './panels/ProposalsPanel'
import PocketPanel from './panels/PocketPanel'
import RunningTimer from './panels/TimerPanel'
import GanttView from './panels/GanttView'
import { Switch } from '../aila-ui'

export default function ProjectsApp() {
  const [me, setMe] = useState(null)
  const [users, setUsers] = useState([])
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [projectId, setProjectId] = useState(null)
  const [project, setProject] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [view, setView] = useState('board')
  const [showProposals, setShowProposals] = useState(false)
  const [showPocket, setShowPocket] = useState(false)
  const [sideOpen, setSideOpen] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  const bump = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    Promise.all([api.me(), api.listUsers().catch(() => [])])
      .then(([m, u]) => { setMe(m); setUsers(u) })
      .catch((e) => setError(e.message))
      .finally(() => setReady(true))
  }, [])

  useEffect(() => {
    if (!projectId) return
    api.getProject(projectId).then(setProject).catch((e) => setError(e.message))
    return () => setProject(null)
  }, [projectId, reloadKey])

  if (!ready) return <div className="pj"><div className="empty">Načítám…</div></div>

  const perms = me?.permissions || []
  const canReviewProposals = can(perms, 'projects.proposal:review')
  const canFinance = can(perms, 'projects.finance:read')
  const canUseAi = can(perms, 'projects.ai:use')

  function pickProject(id) {
    setProjectId(id)
    setSideOpen(false)
  }

  const fc = folderColor(project?.folder_kind)

  return (
    <div className="pj" style={{ '--fc': fc }}>
      <div className="pj-top">
        <button
          type="button"
          className="btn sm pj-hamburger"
          aria-label="Menu"
          onClick={() => setSideOpen((v) => !v)}
        >☰</button>
        <div className="brand"><span className="logo">DL</span> Projekty</div>
        <RunningTimer reloadKey={reloadKey} users={users} onChange={bump} onError={setError} />
        <div className="spacer" />
        {canUseAi && (
          <button type="button" className="btn sm" onClick={() => setShowPocket(true)}>🎙 Pocket</button>
        )}
        {canReviewProposals && (
          <button type="button" className="btn sm" onClick={() => setShowProposals(true)}>⚑ Návrhy AI</button>
        )}
        {me?.user && <span className="who">{me.user.full_name || me.user.username}</span>}
        <a href="/logout" className="btn sm">Odhlásit</a>
      </div>

      {error && (
        <div className="toast pj-toast-err" role="alert">
          <span>{error}</span>
          <button type="button" className="copy" aria-label="Zavřít" onClick={() => setError('')}>×</button>
        </div>
      )}

      <div className={'pj-body' + (sideOpen ? ' side-open' : '')}>
        {sideOpen && <div className="pj-side-scrim" onClick={() => setSideOpen(false)} />}
        <div className="pj-side">
          <ProjectTree
            perms={perms}
            users={users}
            activeId={projectId}
            onSelect={pickProject}
            reloadKey={reloadKey}
            onCreated={(id) => { bump(); pickProject(id) }}
            onError={setError}
          />
        </div>

        <div className="pj-main">
          <div className="pj-viewbar">
            <Switch
              label="Zobrazení"
              value={view}
              onChange={setView}
              options={[['board', 'Nástěnka'], ['timeline', 'Timeline']]}
            />
            {project && <span className="chip">{project.name}</span>}
          </div>

          {project && (
            <div className="pj-proj-head" style={{ marginBottom: '0.2rem' }}>
              <h1>{project.name}</h1>
              <span className="pill s-x">{project.status}</span>
              {project.due_on && <span className="pill st-run">termín {project.due_on}</span>}
            </div>
          )}
          {project?.description && view === 'board' && (
            <p className="muted" style={{ margin: '0.3rem 0 0' }}>{project.description}</p>
          )}

          {view === 'board' && !project && (
            <div className="empty">
              {projectId ? 'Načítám projekt…' : 'Vyber projekt v postranním panelu, nebo přepni na Timeline pro přehled všech projektů.'}
            </div>
          )}
          {view === 'board' && project && (
            <>
              {canFinance && (
                <CostSummary projectId={project.id} reloadKey={reloadKey} onError={setError} />
              )}
              <BoardView
                key={project.id}
                project={project}
                perms={perms}
                users={users}
                reloadKey={reloadKey}
                onOpenTask={setTaskId}
                onChanged={bump}
                onError={setError}
              />
            </>
          )}
          {view === 'timeline' && (
            <GanttView
              key={(project?.id || 'all') + ':' + reloadKey}
              project={project}
              onOpenTask={setTaskId}
              onSelectProject={pickProject}
              onError={setError}
            />
          )}
        </div>
      </div>

      {taskId && (
        <TaskDrawer
          taskId={taskId}
          perms={perms}
          users={users}
          onClose={() => setTaskId(null)}
          onChanged={bump}
          onError={setError}
        />
      )}

      {showProposals && (
        <ProposalsPanel
          users={users}
          onClose={() => setShowProposals(false)}
          onReviewed={bump}
          onError={setError}
        />
      )}

      {showPocket && (
        <PocketPanel
          users={users}
          onClose={() => setShowPocket(false)}
          onProposed={() => { bump(); setShowPocket(false); setShowProposals(true) }}
          onError={setError}
        />
      )}
    </div>
  )
}
