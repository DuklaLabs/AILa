import { createContext, useContext } from 'react'

export const ConfirmContext = createContext(null)

// confirm(message, { title, okLabel, danger }) -> Promise<boolean>
export function useConfirm() {
  return useContext(ConfirmContext)
}
