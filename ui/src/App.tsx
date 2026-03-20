import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import SessionDetail from './pages/SessionDetail'
import Vocab from './pages/Vocab'
import Bank from './pages/Bank'
import Analysis from './pages/Analysis'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/session/:id" element={<SessionDetail />} />
        <Route path="/vocab" element={<Vocab />} />
        <Route path="/bank" element={<Bank />} />
        <Route path="/analysis/:runId" element={<Analysis />} />
      </Route>
    </Routes>
  )
}
