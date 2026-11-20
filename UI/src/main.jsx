import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './theme.css'
import './ui.css'
import './theme-toggle.js'
import './ui.js'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
