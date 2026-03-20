import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getRun, audioUrl } from '../api'
import type { AnalysisRun } from '../types'
import { ComplianceBadge, DriftBadge } from '../components/VerdictBadge'
import FeatureBar from '../components/FeatureBar'
import WaveSurfer from 'wavesurfer.js'

type Region = { start: number; end: number }

interface WaveformProps {
  url: string
  label: string
  brackets: Region[]
  anchors: Region[]
  onReady: (ws: WaveSurfer) => void
}

function WaveformPlayer({ url, label, brackets, anchors, onReady }: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (!containerRef.current) return

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#4a4a60',
      progressColor: '#a855f7',
      cursorColor: '#a855f7',
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 88,
      normalize: true,
    })

    ws.on('ready', () => {
      setReady(true)
      onReady(ws)
    })
    ws.on('play', () => setPlaying(true))
    ws.on('pause', () => setPlaying(false))
    ws.on('finish', () => setPlaying(false))

    ws.load(url)
    wsRef.current = ws

    return () => {
      ws.destroy()
      wsRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  // Redraw overlays whenever ready or regions change
  useEffect(() => {
    if (!ready || !wsRef.current || !containerRef.current) return

    const duration = wsRef.current.getDuration()
    if (!duration) return

    const container = containerRef.current
    container.querySelectorAll('.region-overlay').forEach((el) => el.remove())

    const addOverlay = (
      start: number,
      end: number,
      bg: string,
      border: string,
      labelText: string,
      labelColor: string,
    ) => {
      const pLeft = (start / duration) * 100
      const pWidth = ((end - start) / duration) * 100
      const el = document.createElement('div')
      el.className = 'region-overlay'
      el.style.cssText = `
        position:absolute; top:0; bottom:0;
        left:${pLeft}%; width:${pWidth}%;
        background:${bg};
        pointer-events:none; z-index:2;
        border-left:2px solid ${border};
        border-right:2px solid ${border};
      `
      const tag = document.createElement('span')
      const mins = Math.floor(start / 60)
      const secs = Math.floor(start % 60).toString().padStart(2, '0')
      tag.textContent = `${labelText} ${mins}:${secs}`
      tag.style.cssText = `
        position:absolute; top:2px; left:4px;
        font-size:9px; font-family:monospace;
        color:${labelColor}; white-space:nowrap;
      `
      el.appendChild(tag)
      container.style.position = 'relative'
      container.appendChild(el)
    }

    brackets.forEach((b, i) =>
      addOverlay(b.start, b.end, 'rgba(168,85,247,0.18)', 'rgba(168,85,247,0.7)', `B${i}`, 'rgba(168,85,247,0.9)')
    )
    anchors.forEach((a, i) =>
      addOverlay(a.start, a.end, 'rgba(34,197,94,0.12)', 'rgba(34,197,94,0.5)', `A${i}`, 'rgba(34,197,94,0.8)')
    )
  }, [ready, brackets, anchors])

  return (
    <div className="bg-surface border border-border rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-muted uppercase tracking-wider">{label}</span>
        <button
          onClick={() => wsRef.current?.playPause()}
          className="text-xs px-3 py-1 bg-accent/20 text-accent border border-accent/30 rounded hover:bg-accent/30 disabled:opacity-40 transition-colors"
          disabled={!ready}
        >
          {playing ? '⏸ Pause' : '▶ Play'}
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
  const [zoom, setZoom] = useState(0)

  const origWs = useRef<WaveSurfer | null>(null)
  const varWs = useRef<WaveSurfer | null>(null)
  const syncingScroll = useRef(false)

  useEffect(() => {
    if (!runId) return
    getRun(runId)
      .then((r) => setRun(r.run))
      .catch((e) => setError(e.message))
  }, [runId])

  // Apply zoom to both waveforms
  useEffect(() => {
    origWs.current?.zoom(zoom)
    varWs.current?.zoom(zoom)
  }, [zoom])

  // Wire up scroll sync once both waveforms are ready
  const wireScrollSync = useCallback(() => {
    const a = origWs.current
    const b = varWs.current
    if (!a || !b) return

    a.on('scroll', (visibleStartTime, _visibleEndTime, scrollLeft) => {
      if (syncingScroll.current) return
      syncingScroll.current = true
      const wrapper = (b as unknown as { wrapper: HTMLElement }).wrapper
      if (wrapper) wrapper.scrollLeft = scrollLeft
      syncingScroll.current = false
    })

    b.on('scroll', (visibleStartTime, _visibleEndTime, scrollLeft) => {
      if (syncingScroll.current) return
      syncingScroll.current = true
      const wrapper = (a as unknown as { wrapper: HTMLElement }).wrapper
      if (wrapper) wrapper.scrollLeft = scrollLeft
      syncingScroll.current = false
    })
  }, [])

  const handleOrigReady = useCallback((ws: WaveSurfer) => {
    origWs.current = ws
    if (varWs.current) wireScrollSync()
  }, [wireScrollSync])

  const handleVarReady = useCallback((ws: WaveSurfer) => {
    varWs.current = ws
    if (origWs.current) wireScrollSync()
  }, [wireScrollSync])

  if (error) return <div className="text-fail">Error: {error}</div>
  if (!run) return <div className="text-text-muted">Loading...</div>

  return (
    <div>
      <Link to="/bank" className="text-accent text-sm hover:underline">
        &larr; Back to Bank
      </Link>

      {/* Header */}
      <div className="mt-4 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h2 className="text-xl font-bold font-mono">{run.run_id}</h2>
          {run.source && (
            <span className="text-xs bg-surface-2 border border-border px-2 py-0.5 rounded">
              {run.source}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-sm mb-4">
          <span className="text-accent">{run.intent}</span>
          {run.bracket_results[0] && (
            <>
              <ComplianceBadge verdict={run.bracket_results[0].compliance.verdict} />
              <DriftBadge verdict={run.drift.verdict} />
            </>
          )}
        </div>
      </div>

      {/* Waveforms */}
      <div className="space-y-3 mb-4">
        <WaveformPlayer
          url={audioUrl(run.original_path)}
          label="Original"
          brackets={run.brackets}
          anchors={run.anchors}
          onReady={handleOrigReady}
        />
        <WaveformPlayer
          url={audioUrl(run.variant_path)}
          label="Variant"
          brackets={run.brackets}
          anchors={run.anchors}
          onReady={handleVarReady}
        />
      </div>

      {/* Zoom control */}
      <div className="flex items-center gap-3 mb-6 px-1">
        <span className="text-xs text-text-muted w-10">Zoom</span>
        <input
          type="range"
          min={0}
          max={200}
          step={10}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
          className="flex-1 accent-[#a855f7]"
        />
        <button
          onClick={() => setZoom(0)}
          className="text-xs px-2 py-0.5 border border-border rounded text-text-muted hover:text-text"
        >
          Reset
        </button>
      </div>

      {/* Bracket results */}
      {run.bracket_results.map((br, i) => (
        <div key={i} className="bg-surface border border-border rounded-lg p-4 mb-4">
          <div className="flex items-center gap-3 mb-3">
            <h3 className="text-sm font-bold">Bracket [{br.window}]</h3>
            <ComplianceBadge verdict={br.compliance.verdict} />
            <span className="text-xs text-text-muted">
              score: {br.compliance.score.toFixed(2)} | confidence: {br.compliance.confidence.toFixed(2)}
            </span>
          </div>

          <FeatureBar deltas={br.deltas} />

          {br.compliance.matched_rules.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs text-text-muted uppercase mb-2">Rule Matches</h4>
              <div className="space-y-1">
                {br.compliance.matched_rules.map((rule, j) => (
                  <div key={j} className="text-xs flex items-center gap-2">
                    <span className={rule.met ? 'text-pass' : 'text-fail'}>
                      {rule.met ? '\u2713' : '\u2717'}
                    </span>
                    <span className="text-text-muted">
                      "{rule.keyword}" &rarr; {rule.feature} {rule.expected}
                    </span>
                    <span className="font-mono">
                      (delta: {rule.actual_delta >= 0 ? '+' : ''}{rule.actual_delta.toFixed(3)})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 space-y-1 text-xs">
            <div>
              <span className="text-text-muted">Changed:</span> {br.notes.what_changed}
            </div>
            <div>
              <span className="text-text-muted">Improved:</span> {br.notes.what_improved}
            </div>
            {br.notes.what_got_worse !== 'No obvious artifacts or regressions detected' && (
              <div>
                <span className="text-text-muted">Got worse:</span> {br.notes.what_got_worse}
              </div>
            )}
            <div>
              <span className="text-text-muted">Suggestion:</span> {br.notes.suggested_tweak}
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
                <span className="text-text-muted">Anchor {a.anchor_index}:</span>{' '}
                drift {a.drift_score.toFixed(4)}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-text-muted">
            No anchor regions (track too short or bracket covers full duration)
          </p>
        )}
      </div>
    </div>
  )
}
