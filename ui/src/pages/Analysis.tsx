import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getRun, audioUrl } from '../api'
import type { AnalysisRun } from '../types'
import { ComplianceBadge, DriftBadge } from '../components/VerdictBadge'
import FeatureBar from '../components/FeatureBar'
import WaveSurfer from 'wavesurfer.js'

function WaveformPlayer({
  url,
  label,
  brackets,
  anchors,
}: {
  url: string
  label: string
  brackets: { start: number; end: number }[]
  anchors: { start: number; end: number }[]
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!containerRef.current) return

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#6b6b80',
      progressColor: '#a855f7',
      cursorColor: '#a855f7',
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 80,
      normalize: true,
      backend: 'WebAudio',
    })

    ws.on('ready', () => {
      setReady(true)
    })
    ws.on('play', () => setPlaying(true))
    ws.on('pause', () => setPlaying(false))
    ws.on('finish', () => setPlaying(false))

    ws.load(url)
    wsRef.current = ws

    return () => {
      ws.destroy()
    }
  }, [url])

  // Draw bracket/anchor overlays after ready
  useEffect(() => {
    if (!ready || !wsRef.current || !containerRef.current) return

    const duration = wsRef.current.getDuration()
    if (!duration) return

    const container = containerRef.current
    // Remove old overlays
    container.querySelectorAll('.region-overlay').forEach((el) => el.remove())

    const addOverlay = (
      start: number,
      end: number,
      color: string,
      labelText: string
    ) => {
      const left = (start / duration) * 100
      const width = ((end - start) / duration) * 100
      const el = document.createElement('div')
      el.className = 'region-overlay'
      el.style.cssText = `
        position: absolute; top: 0; bottom: 0;
        left: ${left}%; width: ${width}%;
        background: ${color};
        pointer-events: none; z-index: 2;
        border-left: 2px solid ${color.replace('0.15', '0.6')};
        border-right: 2px solid ${color.replace('0.15', '0.6')};
      `
      const tag = document.createElement('span')
      tag.textContent = labelText
      tag.style.cssText = `
        position: absolute; top: 2px; left: 4px;
        font-size: 10px; color: ${color.replace('0.15', '0.8')};
      `
      el.appendChild(tag)
      container.style.position = 'relative'
      container.appendChild(el)
    }

    brackets.forEach((b, i) =>
      addOverlay(b.start, b.end, 'rgba(168, 85, 247, 0.15)', `B${i}`)
    )
    anchors.forEach((a, i) =>
      addOverlay(a.start, a.end, 'rgba(34, 197, 94, 0.1)', `A${i}`)
    )
  }, [ready, brackets, anchors])

  return (
    <div className="bg-surface border border-border rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-muted uppercase">{label}</span>
        <button
          onClick={() => wsRef.current?.playPause()}
          className="text-xs px-2 py-1 bg-accent/20 text-accent rounded hover:bg-accent/30"
          disabled={!ready}
        >
          {playing ? 'Pause' : 'Play'}
        </button>
      </div>
      <div ref={containerRef} />
    </div>
  )
}

export default function Analysis() {
  const { runId } = useParams<{ runId: string }>()
  const [run, setRun] = useState<AnalysisRun | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    getRun(runId)
      .then((r) => setRun(r.run))
      .catch((e) => setError(e.message))
  }, [runId])

  if (error) {
    return <div className="text-fail">Error: {error}</div>
  }

  if (!run) {
    return <div className="text-text-muted">Loading...</div>
  }

  return (
    <div>
      <Link to="/bank" className="text-accent text-sm hover:underline">
        &larr; Back to Bank
      </Link>

      <div className="mt-4 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-xl font-bold font-mono">{run.run_id}</h2>
          {run.source && (
            <span className="text-xs bg-surface-2 px-2 py-0.5 rounded">
              {run.source}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-sm mb-4">
          <span className="text-accent">{run.intent}</span>
          {run.bracket_results[0] && (
            <>
              <ComplianceBadge
                verdict={run.bracket_results[0].compliance.verdict}
              />
              <DriftBadge verdict={run.drift.verdict} />
            </>
          )}
        </div>
      </div>

      {/* Waveforms */}
      <div className="space-y-3 mb-6">
        <WaveformPlayer
          url={audioUrl(run.original_path)}
          label="Original"
          brackets={run.brackets}
          anchors={run.anchors}
        />
        <WaveformPlayer
          url={audioUrl(run.variant_path)}
          label="Variant"
          brackets={run.brackets}
          anchors={run.anchors}
        />
      </div>

      {/* Bracket results */}
      {run.bracket_results.map((br, i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded-lg p-4 mb-4"
        >
          <div className="flex items-center gap-3 mb-3">
            <h3 className="text-sm font-bold">
              Bracket [{br.window}]
            </h3>
            <ComplianceBadge verdict={br.compliance.verdict} />
            <span className="text-xs text-text-muted">
              score: {br.compliance.score.toFixed(2)} | confidence:{' '}
              {br.compliance.confidence.toFixed(2)}
            </span>
          </div>

          <FeatureBar deltas={br.deltas} />

          {/* Matched rules */}
          {br.compliance.matched_rules.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs text-text-muted uppercase mb-2">
                Rule Matches
              </h4>
              <div className="space-y-1">
                {br.compliance.matched_rules.map((rule, j) => (
                  <div
                    key={j}
                    className="text-xs flex items-center gap-2"
                  >
                    <span className={rule.met ? 'text-pass' : 'text-fail'}>
                      {rule.met ? '\u2713' : '\u2717'}
                    </span>
                    <span className="text-text-muted">
                      "{rule.keyword}" &rarr; {rule.feature}{' '}
                      {rule.expected}
                    </span>
                    <span className="font-mono">
                      (delta: {rule.actual_delta >= 0 ? '+' : ''}
                      {rule.actual_delta.toFixed(3)})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          <div className="mt-4 space-y-1 text-xs">
            <div>
              <span className="text-text-muted">Changed:</span>{' '}
              {br.notes.what_changed}
            </div>
            <div>
              <span className="text-text-muted">Improved:</span>{' '}
              {br.notes.what_improved}
            </div>
            {br.notes.what_got_worse !==
              'No obvious artifacts or regressions detected' && (
              <div>
                <span className="text-text-muted">Got worse:</span>{' '}
                {br.notes.what_got_worse}
              </div>
            )}
            <div>
              <span className="text-text-muted">Suggestion:</span>{' '}
              {br.notes.suggested_tweak}
            </div>
          </div>
        </div>
      ))}

      {/* Drift */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center gap-3 mb-2">
          <h3 className="text-sm font-bold">Drift</h3>
          <DriftBadge verdict={run.drift.verdict} />
          <span className="text-xs text-text-muted">
            overall: {run.drift.overall_drift.toFixed(4)}
          </span>
        </div>

        {run.drift.per_anchor.length > 0 ? (
          <div className="space-y-2">
            {run.drift.per_anchor.map((a) => (
              <div key={a.anchor_index} className="text-xs">
                <span className="text-text-muted">
                  Anchor {a.anchor_index}:
                </span>{' '}
                drift {a.drift_score.toFixed(4)}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-text-muted">
            No anchor regions (track too short or bracket covers full
            duration)
          </p>
        )}
      </div>
    </div>
  )
}
