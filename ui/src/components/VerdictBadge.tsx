import type { ComplianceVerdict, DriftVerdict } from '../types'

const complianceColors: Record<ComplianceVerdict, string> = {
  PASS: 'bg-pass/20 text-pass border-pass/30',
  MIXED: 'bg-mixed/20 text-mixed border-mixed/30',
  FAIL: 'bg-fail/20 text-fail border-fail/30',
}

const driftColors: Record<DriftVerdict, string> = {
  LOW: 'bg-low/20 text-low border-low/30',
  MED: 'bg-med/20 text-med border-med/30',
  HIGH: 'bg-high/20 text-high border-high/30',
}

export function ComplianceBadge({ verdict }: { verdict: ComplianceVerdict }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-bold border ${complianceColors[verdict]}`}
    >
      {verdict}
    </span>
  )
}

export function DriftBadge({ verdict }: { verdict: DriftVerdict }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-xs font-bold border ${driftColors[verdict]}`}
    >
      {verdict}
    </span>
  )
}
