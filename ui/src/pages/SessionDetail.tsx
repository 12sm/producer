import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getSession } from '../api'
import type { Session } from '../types'
import { ComplianceBadge, DriftBadge } from '../components/VerdictBadge'

export default function SessionDetail() {
  const { id } = useParams<{ id: string }>()
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getSession(id)
      .then(setSession)
      .catch((e) => setError(e.message))
  }, [id])

  if (error) {
    return (
      <div className="text-fail">
        Error loading session: {error}
      </div>
    )
  }

  if (!session) {
    return <div className="text-text-muted">Loading...</div>
  }

  return (
    <div>
      <Link to="/" className="text-accent text-sm hover:underline">
        &larr; Back
      </Link>

      <div className="mt-4 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-xl font-bold">{session.session_id}</h2>
          <span
            className={`text-xs px-2 py-0.5 rounded ${
              session.status === 'accepted'
                ? 'bg-pass/20 text-pass'
                : session.status === 'active'
                  ? 'bg-accent/20 text-accent'
                  : 'bg-text-muted/20 text-text-muted'
            }`}
          >
            {session.status}
          </span>
        </div>

        <div className="bg-surface border border-border rounded-lg p-4 text-sm space-y-1">
          <div>
            <span className="text-text-muted">Prompt:</span>{' '}
            {session.prompt}
          </div>
          <div>
            <span className="text-text-muted">Intent:</span>{' '}
            <span className="text-accent">{session.intent}</span>
          </div>
          <div>
            <span className="text-text-muted">Brackets:</span>{' '}
            {session.brackets.join(', ')}
          </div>
          <div>
            <span className="text-text-muted">Targets:</span>{' '}
            compliance &ge; {session.target_compliance}, drift &le;{' '}
            {session.target_drift}
          </div>
        </div>
      </div>

      {/* Iteration timeline */}
      <h3 className="text-sm text-text-muted uppercase tracking-wider mb-3">
        Iterations
      </h3>

      <div className="relative pl-6 border-l-2 border-border space-y-4">
        {session.iterations.map((it) => {
          const isAccepted = session.accepted_run === it.run_id

          return (
            <div key={it.iteration} className="relative">
              {/* Timeline dot */}
              <div
                className={`absolute -left-[25px] top-2 w-3 h-3 rounded-full border-2 ${
                  isAccepted
                    ? 'bg-pass border-pass'
                    : 'bg-surface border-accent'
                }`}
              />

              <div className="bg-surface border border-border rounded-lg p-4">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mb-2">
                  <span className="text-sm font-bold">#{it.iteration}</span>
                  <ComplianceBadge verdict={it.compliance_verdict} />
                  <DriftBadge verdict={it.drift_verdict} />
                  {isAccepted && (
                    <span className="text-pass text-xs font-bold">
                      ★ accepted
                    </span>
                  )}
                  <span className="text-xs text-text-muted ml-auto">
                    {new Date(it.timestamp).toLocaleString()}
                  </span>
                </div>

                <p className="text-sm text-text-muted mb-1 truncate">
                  {it.variant_prompt}
                </p>

                <div className="flex items-center gap-4 text-xs mb-2">
                  <span>
                    compliance:{' '}
                    <span className="text-text font-bold">
                      {it.compliance_score.toFixed(2)}
                    </span>
                  </span>
                  <span>
                    drift:{' '}
                    <span className="text-text font-bold">
                      {it.drift_score.toFixed(3)}
                    </span>
                  </span>
                  {it.met_targets && (
                    <span className="text-pass">met targets</span>
                  )}
                </div>

                {it.notes && (
                  <p className="text-xs text-text-muted italic">
                    "{it.notes}"
                  </p>
                )}

                <Link
                  to={`/analysis/${it.run_id}`}
                  className="inline-block mt-2 text-xs text-accent hover:underline"
                >
                  View Analysis &rarr;
                </Link>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
