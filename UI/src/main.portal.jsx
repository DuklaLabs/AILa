import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import LabOrchestratorDashboard from './LabOrchestratorDashboard.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LabOrchestratorDashboard />
  </StrictMode>,
)
