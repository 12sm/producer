import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getRun, audioUrl } from '../api'
import type { AnalysisRun } from '../types'
import { ComplianceBadge, DriftBadge } from '../components/VerdictBadge'
import FeatureBar from '../components/FeatureBar'
import WaveSurfer from 'wavesurfer.js'

type Region = { start: number; end: number }

function formatTime(s: number) {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60).toString().padStart(2, '0')
  return `${m}:${sec}`
}

interface WaveformProps {
  url: string
  label: string
  brackets: Region[]
  anchors: Region[]
  onReady: (ws: WaveSurfer) => void
  onPlay?: () => void
  onBracketClick?: (index: number, start: number) => void
}

function WaveformPlayer({
  url,
  label,
  brackets,
  anchors,
  onReady,
  onPlay,
  onBracketClick,
}: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const [playing, setPlaying] = useState(false)
  const [ready, setReady] = useState(false)
  const onPlayRef = useRef(onPlay)
  const onBracketClickRef = useRef(onBracketClick)

  useEffect(() => { onPlayRef.current = onPlay }, [onPlay])
  useEffect(() => { onBracketClickRef.current = onBracketClick }, [onBracketClick])

  useEffect(() => {
    if (!containerRef.current) return

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#3d3d55',
      progressColor: '#a855f7',
      cursorColor: '#e0e0ff',
      cursorWidth: 2,
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
    ws.on('play', () => {
      setPlaying(true)
      onPlayRef.current?.()
    })
    ws.on('pause', () => setPlaying(false))
    ws.on('finish', () => setPlaying(false))

    ws.load(url)
    wsRef.current = ws

    return () => {
      ws.destroy()
      wsRef.current = null
      setReady(false)
      setPlaying(false)
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
      _labelText: string,
      labelColor: string,
      bracketIndex: number | null,
    ) => {
      const pLeft = (start / duration) * 100
      const pWidth = ((end - start) / duration) * 100
      const el = document.createElement('div')
      el.className = 'region-overlay'
      const clickable = bracketIndex !== null
      el.style.cssText = `
        position:absolute; top:0; bottom:0;
        left:${pLeft}%; width:${pWidth}%;
        background:${bg};
        z-index:2;
        border-left:2px solid ${border};
        border-right:2px solid ${border};
        ${clickable ? 'cursor:pointer;' : 'pointer-events:none;'}
        transition: background 0.1s;
      `
      if (clickable) {
        el.addEventListener('mouseenter', () => {
          el.style.background = bg.replace('0.18', '0.32').replace('0.12', '0.22')
        })
        el.addEventListener('mouseleave', () => {
          el.style.background = bg
        })
        el.addEventListener('click', (e) => {
          e.stopPropagation()
          onBracketClickRef.current?.(bracketIndex, start)
        })
      }

      const tag = document.createElement('span')
      tag.textContent = `B${bracketIndex ?? ''} ${formatTime(start)}–${formatTime(end)}`
      tag.style.cssText = `
        position:absolute; top:3px; left:5px;
        font-size:9px; font-family:monospace;
        color:${labelColor}; white-space:nowrap;
        pointer-events:none;
      `
      el.appendChild(tag)
      container.style.position = 'relative'
      container.appendChild(el)
    }

    brackets.forEach((b, i) =>
      addOverlay(
        b.start, b.end,
        'rgba(168,85,247,0.18)', 'rgba(168,85,247,0.6)',
        `B${i}`, 'rgba(200,160,255,0.95)',
        i,
      )
    )
    anchors.forEach((a, i) =>
      addOverlay(
        a.start, a.end,
        'rgba(34,197,94,0.12)', 'rgba(34,197,94,0.45)',
        `A${i}`, 'rgba(100,220,130,0.9)',
        null,
      )
    )
  }, [ready, brackets, anchors])

  return (
    <div className="bg-surface border border-border rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-muted uppercase tracking-wider font-mono">
          {label}
        </span>
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
  const [activeSide, setActiveSide] = useState<'A' | 'B' | null>(null)

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

  // Wire scroll sync using getWrapper() — called once both are ready
  const wireScrollSync = useCallback(() => {
    const a = origWs.current
    const b = varWs.current
    if (!a || !b) return

    const wrapA = a.getWrapper()
    const wrapB = b.getWrapper()
    if (!wrapA || !wrapB) return

    wrapA.addEventListener('scroll', () => {
      if (syncingScroll.current) return
      syncingScroll.current = true
      wrapB.scrollLeft = wrapA.scrollLeft
      syncingScroll.current = false
    })
    wrapB.addEventListener('scroll', () => {
      if (syncingScroll.current) return
      syncingScroll.current = true
      wrapA.scrollLeft = wrapB.scrollLeft
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

  // A/B mutual-exclusion: when one plays, pause the other
  const handleOrigPlay = useCallback(() => {
    varWs.current?.pause()
    setActiveSide('A')
  }, [])

  const handleVarPlay = useCallback(() => {
    origWs.current?.pause()
    setActiveSide('B')
  }, [])

  // Seek both to a bracket start; optionally play one side
  const seekBoth = useCallback((start: number) => {
    origWs.current?.setTime(start)
    varWs.current?.setTime(start)
  }, [])

  const playFrom = useCallback((side: 'A' | 'B', start: number) => {
    seekBoth(start)
    if (side === 'A') {
      varWs.current?.pause()
      origWs.current?.play()
    } else {
      origWs.current?.pause()
      varWs.current?.play()
    }
  }, [seekBoth])

  // Clicking a bracket overlay seeks both; then plays whichever side is active
  const handleBracketClick = useCallback((_i: number, start: number) => {
    seekBoth(start)
    // If something is already playing, keep playing on that side
    if (activeSide === 'A') origWs.current?.play()
    else if (activeSide === 'B') varWs.current?.play()
  }, [seekBoth, activeSide])

  if (error) return <div className="text-fail">Error: {error}</div>
  if (!run) return <div className="text-text-muted">Loading...</div>

  const brackets = run.brackets

  return (
    <div>
      <Link to="/bank" className="text-accent text-sm hover:underline">
        &larr; Back to Bank
      </Link>

      {/* Header */}
      <div className="mt-4 mb-5">
        <div className="flex flex-wrap items-center gap-3 mb-2">
          <h2 className="text-xl font-bold font-mono">{run.run_id}</h2>
          {run.source && (
            <span className="text-xs bg-surface-2 border border-border px-2 py-0.5 rounded">
              {run.source}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
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
      <div className="space-y-3 mb-3">
        <WaveformPlayer
          url={audioUrl(run.original_path)}
          label="A — Original"
          brackets={run.brackets}
          anchors={run.anchors}
          onReady={handleOrigReady}
          onPlay={handleOrigPlay}
          onBracketClick={handleBracketClick}
        />
        <WaveformPlayer
          url={audioUrl(run.variant_path)}
          label="B — Variant"
          brackets={run.brackets}
          anchors={run.anchors}
          onReady={handleVarReady}
          onPlay={handleVarPlay}
          onBracketClick={handleBracketClick}
        />
      </div>

      {/* A/B + bracket controls */}
      <div className="bg-surface border border-border rounded-lg px-3 py-2.5 mb-3 flex flex-wrap items-center gap-2">
        {/* Active indicator */}
        <span className="text-xs text-text-muted mr-1">A/B:</span>
        <button
          onClick={() => {
            origWs.current?.play()
          }}
          className={`text-xs px-3 py-1 rounded border transition-colors ${
            activeSide === 'A'
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-text-muted border-border hover:text-text'
          }`}
        >
          ▶ A
        </button>
        <button
          onClick={() => {
            varWs.current?.play()
          }}
          className={`text-xs px-3 py-1 rounded border transition-colors ${
            activeSide === 'B'
              ? 'bg-accent text-white border-accent'
              : 'bg-surface-2 text-text-muted border-border hover:text-text'
          }`}
        >
          ▶ B
        </button>

        <span className="text-border mx-1">|</span>

        {/* Bracket jump buttons */}
        <span className="text-xs text-text-muted">Jump:</span>
        {brackets.map((b, i) => (
          <button
            key={i}
            onClick={() => seekBoth(b.start)}
            className="text-xs px-2 py-1 rounded border border-accent/40 text-accent hover:bg-accent/10 transition-colors font-mono"
          >
            B{i} {formatTime(b.start)}
          </button>
        ))}
        {brackets.map((b, i) => (
          <button
            key={`ab-${i}`}
            onClick={() => playFrom('A', b.start)}
            className="text-xs px-2 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 transition-colors font-mono"
            title={`Play A from ${formatTime(b.start)}`}
          >
            A@B{i}
          </button>
        ))}
        {brackets.map((b, i) => (
          <button
            key={`bb-${i}`}
            onClick={() => playFrom('B', b.start)}
            className="text-xs px-2 py-0.5 rounded bg-surface-2 text-text-muted hover:text-text hover:bg-surface-2 transition-colors border border-border font-mono"
            title={`Play B from ${formatTime(b.start)}`}
          >
            B@B{i}
          </button>
        ))}

        <span className="text-border mx-1">|</span>

        {/* Zoom */}
        <span className="text-xs text-text-muted">Zoom</span>
        <input
          type="range"
          min={0}
          max={200}
          step={10}
          value={zoom}
          onChange={(e) => setZoom(Number(e.target.value))}
          className="w-24 accent-[#a855f7]"
        />
        <button
          onClick={() => setZoom(0)}
          className="text-xs px-2 py-0.5 border border-border rounded text-text-muted hover:text-text"
        >
          Reset
        </button>
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-text-muted mb-5 px-1">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-accent/30 border border-accent/60" />
          Bracket region (click to seek)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm bg-pass/20 border border-pass/40" />
          Anchor region
        </span>
      </div>

      {/* Bracket results */}
      {run.bracket_results.map((br, i) => (
        <div key={i} className="bg-surface border border-border rounded-lg p-4 mb-4">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <h3 className="text-sm font-bold font-mono">
              [{br.window}]
            </h3>
            <ComplianceBadge verdict={br.compliance.verdict} />
            <span className="text-xs text-text-muted">
              score: {br.compliance.score.toFixed(2)} | confidence: {br.compliance.confidence.toFixed(2)}
            </span>
            <button
              onClick={() => playFrom('A', br.start)}
              className="ml-auto text-xs px-2 py-0.5 rounded bg-accent/10 text-accent hover:bg-accent/20 border border-accent/20 font-mono"
            >
              ▶ A
            </button>
            <button
              onClick={() => playFrom('B', br.start)}
              className="text-xs px-2 py-0.5 rounded border border-border text-text-muted hover:text-text font-mono"
            >
              ▶ B
            </button>
          </div>

          <FeatureBar deltas={br.deltas} />

          {br.compliance.matched_rules.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs text-text-muted uppercase mb-2">Rule Matches</h4>
              <div className="space-y-1">
                {br.compliance.matched_rules.map((rule, j) => (
                  <div key={j} className="text-xs flex items-center gap-2">
                    <span className={rule.met ? 'text-pass' : 'text-fail'}>
                      {rule.met ? '✓' : '✗'}
                    </span>
                    <span className="text-text-muted">
                      "{rule.keyword}" → {rule.feature} {rule.expected}
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
      <div className="bg-surface border border-border rounded-lg p-4 mb-6">
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
