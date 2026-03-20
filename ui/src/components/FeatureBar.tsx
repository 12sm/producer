import { FEATURE_LABELS, type FeatureDeltas, type FeatureKey } from '../types'

const FEATURES: FeatureKey[] = [
  'rms_mean',
  'rms_std',
  'centroid_mean',
  'onset_density',
  'tempo',
]

interface Props {
  deltas: FeatureDeltas
  maxDelta?: number
}

export default function FeatureBar({ deltas, maxDelta = 2.0 }: Props) {
  return (
    <div className="flex flex-col gap-1.5">
      {FEATURES.map((key) => {
        const val = deltas[key] ?? 0
        const pct = Math.min(Math.abs(val) / maxDelta, 1) * 100
        const positive = val >= 0

        return (
          <div key={key} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-text-muted shrink-0 text-right">
              {FEATURE_LABELS[key]}
            </span>
            <div className="flex-1 h-3 bg-surface rounded overflow-hidden relative">
              <div
                className={`h-full rounded ${positive ? 'bg-pass/60' : 'bg-fail/60'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span
              className={`w-16 text-right font-mono ${positive ? 'text-pass' : 'text-fail'}`}
            >
              {val >= 0 ? '+' : ''}
              {(val * 100).toFixed(0)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}
