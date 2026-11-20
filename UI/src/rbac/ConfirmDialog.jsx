import { useCallback, useEffect, useRef, useState } from 'react'
import { ConfirmContext } from './confirmContext'

// Promise-based replacement for window.confirm() built on the shared <dialog> styling.
export default function ConfirmProvider({ children }) {
  const ref = useRef(null)
  const [state, setState] = useState(null)

  const confirm = useCallback(
    (message, opts = {}) => new Promise((resolve) => setState({ message, ...opts, resolve })),
    [],
  )

  useEffect(() => {
    const d = ref.current
    if (state && d && !d.open) d.showModal()
  }, [state])

  function close(value) {
    const s = state
    if (ref.current?.open) ref.current.close()
    setState(null)
    s?.resolve(value)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <dialog ref={ref} onCancel={(e) => { e.preventDefault(); close(false) }}>
        {state && (
          <form method="dialog" onSubmit={(e) => { e.preventDefault(); close(true) }}>
            <h3>{state.title || 'Potvrdit'}</h3>
            <p className="rbac-msg">{state.message}</p>
            <div className="dlg-actions">
              <button type="button" className="btn" onClick={() => close(false)}>Zrušit</button>
              <button type="submit" autoFocus className={state.danger ? 'btn danger armed' : 'btn primary'}>
                {state.okLabel || 'OK'}
              </button>
            </div>
          </form>
        )}
      </dialog>
    </ConfirmContext.Provider>
  )
}
