import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSessions, listAllRuns, getVocab } from '../api'
import type { Session, VocabIndex } from '../types'
import { ComplianceBadge, DriftBadge } from '../components/VerdictBadge'

interface Stats {
  sessions: number
  accepted: number
  keywords: number
  runs: number
}

export default function Dashboard() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [stats, setStats] = useState<Stats>({
    sessions: 0,
    accepted: 0,
    keywords: 0,
    runs: 0,
  })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.allSettled([listSessions(), listAllRuns(), getVocab()]).then(
      ([sessRes, runsRes, vocabRes]) => {
        if (sessRes.status === 'fulfilled') {
          const s = sessRes.value.sessions ?? []
          setSessions(s)
          setStats((prev) => ({
            ...prev,
            sessions: s.length,
            accepted: s.filter((x) => x.status === 'accepted').length,
          }))
        }
        if (runsRes.status === 'fulfilled') {
          setStats((prev) => ({
            ...prev,
            runs: runsRes.value.count ?? runsRes.value.runs?.length ?? 0,
          }))
        }
        if (vocabRes.status === 'fulfilled') {
          const v = vocabRes.value as VocabIndex
          setStats((prev) => ({
            ...prev,
            keywords: Object.keys(v.keywords ?? {}).length,
          }))
        }
        const anyFailed = [sessRes, runsRes, vocabRes].some(
          (r) => r.status === 'rejected'
        )
        if (anyFailed) {
          setError(
            'Some data failed to load. Is the bridge server running on :7862?'
          )
        }
      }
    )
  }, [])

  const statCards = [
    { label: 'Sessions', value: stats.sessions },
    { label: 'Accepted', value: stats.accepted },
    { label: 'Keywords', value: stats.keywords },
    { label: 'Runs', value: stats.runs },
  ]

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Dashboard</h2>

      {error && (
        <div className="bg-fail/10 border border-fail/30 text-fail px-4 py-2 rounded mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        {statCards.map(({ label, value }) => (
          <div
            key={label}
            className="bg-surface rounded-lg border border-border p-4 text-center"
          >
            <div className="text-2xl font-bold text-accent">{value}</div>
            <div className="text-xs text-text-muted mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Sessions list */}
      <h3 className="text-sm text-text-muted uppercase tracking-wider mb-3">
        Sessions
      </h3>

      {sessions.length === 0 && !error && (
        <p className="text-text-muted text-sm">
          No sessions yet. Run a bracket lab analysis to get started.
        </p>
      )}

      <div className="flex flex-col gap-2">
        {sessions.map((s) => (
          <Link
            key={s.session_id}
            to={`/session/${s.session_id}`}
            className="bg-surface hover:bg-surface-2 border border-border rounded-lg p-4 transition-colors block"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full ${
                    s.status === 'accepted'
                      ? 'bg-pass'
                      : s.status === 'active'
                        ? 'bg-accent'
                        : 'bg-text-muted'
                  }`}
                />
                <span className="text-sm font-bold">{s.session_id}</span>
                <span className="text-xs text-text-muted">{s.status}</span>
              </div>
              <span className="text-xs text-text-muted">
                {s.iterations.length}/{s.max_iterations} iterations
              </span>
            </div>

            <p className="text-sm text-text-muted truncate mb-1">{s.prompt}</p>

            <div className="flex items-center gap-2 text-xs">
              <span className="text-accent">{s.intent}</span>
              {s.iterations.length > 0 && (
                <>
                  <span className="text-text-muted">|</span>
                  <span>Best:</span>
                  <ComplianceBadge
                    verdict={
                      s.iterations.reduce((best, it) =>
                        it.compliance_score > best.compliance_score ? it : best
                      ).compliance_verdict
                    }
                  />
                  <DriftBadge
                    verdict={
                      s.iterations.reduce((best, it) =>
                        it.drift_score < best.drift_score ? it : best
                      ).drift_verdict
                    }
                  />
                </>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
