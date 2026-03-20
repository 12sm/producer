import { useEffect, useState } from 'react'
import { getVocab, buildVocab } from '../api'
import type { VocabIndex, KeywordEntry, FeatureKey } from '../types'
import { FEATURE_LABELS } from '../types'
import FeatureBar from '../components/FeatureBar'

export default function Vocab() {
  const [vocab, setVocab] = useState<VocabIndex | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [building, setBuilding] = useState(false)

  const load = () => {
    getVocab()
      .then(setVocab)
      .catch((e) => setError(e.message))
  }

  useEffect(load, [])

  const handleRebuild = async () => {
    setBuilding(true)
    try {
      await buildVocab()
      load()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBuilding(false)
    }
  }

  if (error) {
    return <div className="text-fail">Error: {error}</div>
  }

  if (!vocab) {
    return <div className="text-text-muted">Loading...</div>
  }

  const keywords = Object.entries(vocab.keywords)
    .filter(([k]) => k.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => b[1].count - a[1].count)

  const selectedEntry: KeywordEntry | null =
    selected && vocab.keywords[selected] ? vocab.keywords[selected] : null

  // Find the max delta across all keywords for consistent bar scaling
  const maxDelta = Math.max(
    0.5,
    ...Object.values(vocab.keywords).flatMap((k) =>
      Object.values(k.avg_deltas).map(Math.abs)
    )
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold">Vocabulary</h2>
          <p className="text-sm text-text-muted">
            {Object.keys(vocab.keywords).length} keywords from{' '}
            {vocab.total_runs} observations
          </p>
        </div>
        <button
          onClick={handleRebuild}
          disabled={building}
          className="px-3 py-1.5 text-sm bg-accent/20 text-accent border border-accent/30 rounded hover:bg-accent/30 disabled:opacity-50 transition-colors"
        >
          {building ? 'Rebuilding...' : 'Rebuild Index'}
        </button>
      </div>

      <input
        type="text"
        placeholder="Search keywords..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full mb-4 px-3 py-2 bg-surface border border-border rounded text-sm text-text placeholder-text-muted focus:outline-none focus:border-accent"
      />

      <div className="grid grid-cols-[1fr_300px] gap-4">
        {/* Keyword table */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-text-muted text-xs uppercase">
                <th className="text-left p-3">Keyword</th>
                <th className="text-right p-3 w-16">Obs</th>
                <th className="text-right p-3 w-16">Pass%</th>
                <th className="p-3 w-48">Top Effect</th>
              </tr>
            </thead>
            <tbody>
              {keywords.map(([keyword, entry]) => {
                const topEffect = (
                  Object.entries(entry.avg_deltas) as [FeatureKey, number][]
                )
                  .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
                  .at(0)

                return (
                  <tr
                    key={keyword}
                    onClick={() => setSelected(keyword)}
                    className={`border-b border-border cursor-pointer transition-colors ${
                      selected === keyword
                        ? 'bg-accent-dim'
                        : 'hover:bg-surface-2'
                    }`}
                  >
                    <td className="p-3 font-bold">{keyword}</td>
                    <td className="p-3 text-right text-text-muted">
                      {entry.count}
                    </td>
                    <td className="p-3 text-right">
                      <span
                        className={
                          entry.pass_rate >= 0.7
                            ? 'text-pass'
                            : entry.pass_rate >= 0.4
                              ? 'text-mixed'
                              : 'text-fail'
                        }
                      >
                        {(entry.pass_rate * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="p-3 text-xs text-text-muted">
                      {topEffect && (
                        <>
                          {FEATURE_LABELS[topEffect[0]]}{' '}
                          <span
                            className={
                              topEffect[1] >= 0 ? 'text-pass' : 'text-fail'
                            }
                          >
                            {topEffect[1] >= 0 ? '+' : ''}
                            {(topEffect[1] * 100).toFixed(0)}%
                          </span>
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        <div className="bg-surface border border-border rounded-lg p-4">
          {selectedEntry ? (
            <>
              <h3 className="text-lg font-bold mb-1">{selected}</h3>
              <p className="text-xs text-text-muted mb-4">
                {selectedEntry.count} observations,{' '}
                {(selectedEntry.pass_rate * 100).toFixed(0)}% pass rate
              </p>

              <h4 className="text-xs text-text-muted uppercase mb-2">
                Feature Effects
              </h4>
              <FeatureBar
                deltas={selectedEntry.avg_deltas}
                maxDelta={maxDelta}
              />

              {selectedEntry.associated_intents.length > 0 && (
                <>
                  <h4 className="text-xs text-text-muted uppercase mt-4 mb-2">
                    Associated Intents
                  </h4>
                  <div className="flex flex-wrap gap-1">
                    {selectedEntry.associated_intents.map((intent) => (
                      <span
                        key={intent}
                        className="text-xs bg-surface-2 px-2 py-0.5 rounded"
                      >
                        {intent}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </>
          ) : (
            <p className="text-sm text-text-muted">
              Select a keyword to see details
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
