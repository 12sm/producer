import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listAllRuns, searchBank } from '../api'
import type { BankEntry, ComplianceVerdict, DriftVerdict } from '../types'
import { ComplianceBadge, DriftBadge } from '../components/VerdictBadge'

export default function Bank() {
  const [runs, setRuns] = useState<BankEntry[]>([])
  const [search, setSearch] = useState('')
  const [compFilter, setCompFilter] = useState<ComplianceVerdict | ''>('')
  const [driftFilter, setDriftFilter] = useState<DriftVerdict | ''>('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listAllRuns()
      .then((r) => setRuns(r.runs ?? []))
      .catch((e) => setError(e.message))
  }, [])

  const handleSearch = async () => {
    if (!search.trim()) {
      listAllRuns().then((r) => setRuns(r.runs ?? []))
      return
    }
    try {
      const result = await searchBank(search)
      setRuns(result.results ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const filtered = runs.filter((r) => {
    if (compFilter && r.compliance_verdict !== compFilter) return false
    if (driftFilter && r.drift_verdict !== driftFilter) return false
    return true
  })

  if (error) {
    return <div className="text-fail">Error: {error}</div>
  }

  return (
    <div>
      <h2 className="text-xl font-bold mb-1">Snippet Bank</h2>
      <p className="text-sm text-text-muted mb-4">{runs.length} runs</p>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          placeholder="Search by intent..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          className="flex-1 px-3 py-2 bg-surface border border-border rounded text-sm text-text placeholder-text-muted focus:outline-none focus:border-accent"
        />
        <select
          value={compFilter}
          onChange={(e) =>
            setCompFilter(e.target.value as ComplianceVerdict | '')
          }
          className="px-3 py-2 bg-surface border border-border rounded text-sm text-text focus:outline-none"
        >
          <option value="">All compliance</option>
          <option value="PASS">PASS</option>
          <option value="MIXED">MIXED</option>
          <option value="FAIL">FAIL</option>
        </select>
        <select
          value={driftFilter}
          onChange={(e) =>
            setDriftFilter(e.target.value as DriftVerdict | '')
          }
          className="px-3 py-2 bg-surface border border-border rounded text-sm text-text focus:outline-none"
        >
          <option value="">All drift</option>
          <option value="LOW">LOW</option>
          <option value="MED">MED</option>
          <option value="HIGH">HIGH</option>
        </select>
      </div>

      {/* Runs table */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-text-muted text-xs uppercase">
              <th className="text-left p-3">Run ID</th>
              <th className="text-left p-3">Intent</th>
              <th className="text-left p-3">Brackets</th>
              <th className="text-center p-3 w-20">Comp</th>
              <th className="text-center p-3 w-20">Drift</th>
              <th className="text-right p-3 w-32">Time</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((run) => (
              <tr
                key={run.run_id}
                className="border-b border-border hover:bg-surface-2 transition-colors"
              >
                <td className="p-3">
                  <Link
                    to={`/analysis/${run.run_id}`}
                    className="text-accent hover:underline font-mono text-xs"
                  >
                    {run.run_id.slice(0, 15)}...
                  </Link>
                </td>
                <td className="p-3 text-text-muted truncate max-w-48">
                  {run.intent}
                </td>
                <td className="p-3 text-text-muted text-xs">
                  {run.brackets.join(', ')}
                </td>
                <td className="p-3 text-center">
                  <ComplianceBadge verdict={run.compliance_verdict} />
                </td>
                <td className="p-3 text-center">
                  <DriftBadge verdict={run.drift_verdict} />
                </td>
                <td className="p-3 text-right text-xs text-text-muted">
                  {new Date(run.timestamp).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <p className="p-4 text-sm text-text-muted text-center">
            No runs match filters
          </p>
        )}
      </div>
    </div>
  )
}
