import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '../../src/auth/AuthContext'
import '../../src/index.css'
import PharmacyApp from './PharmacyApp'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <PharmacyApp />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
