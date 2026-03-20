// ── Audio Features ──────────────────────────────────────────

export interface AudioFeatures {
  rms_mean: number
  rms_std: number
  centroid_mean: number
  centroid_std: number
  onset_strength_mean: number
  onset_density: number
  tempo: number
}

export type FeatureKey = keyof AudioFeatures

export const FEATURE_LABELS: Record<FeatureKey, string> = {
  rms_mean: 'Loudness',
  rms_std: 'Dynamics',
  centroid_mean: 'Brightness',
  centroid_std: 'Brightness Var',
  onset_strength_mean: 'Onset Strength',
  onset_density: 'Onsets/sec',
  tempo: 'Tempo',
}

export type FeatureDeltas = Record<FeatureKey, number>

// ── Compliance ──────────────────────────────────────────────

export type ComplianceVerdict = 'PASS' | 'MIXED' | 'FAIL'
export type DriftVerdict = 'LOW' | 'MED' | 'HIGH'

export interface MatchedRule {
  keyword: string
  feature: string
  expected: string
  actual_delta: number
  met: boolean
}

export interface Compliance {
  score: number
  confidence: number
  verdict: ComplianceVerdict
  explanation: string
  matched_rules: MatchedRule[]
}

export interface ProducerNotes {
  window: string
  what_changed: string
  what_improved: string
  what_got_worse: string
  suggested_tweak: string
}

// ── Bracket Results ─────────────────────────────────────────

export interface BracketResult {
  window: string
  start: number
  end: number
  original_features: AudioFeatures
  variant_features: AudioFeatures
  deltas: FeatureDeltas
  compliance: Compliance
  notes: ProducerNotes
}

export interface AnchorDrift {
  anchor_index: number
  drift_score: number
  deltas: FeatureDeltas
}

export interface Drift {
  per_anchor: AnchorDrift[]
  overall_drift: number
  verdict: DriftVerdict
}

// ── Analysis Run ────────────────────────────────────────────

export type AudioSource = 'suno' | 'elevenlabs' | 'manual'

export interface AnalysisRun {
  run_id: string
  timestamp: string
  original_path: string
  variant_path: string
  prompt_text: string
  intent: string
  source?: AudioSource
  brackets: { start: number; end: number }[]
  anchors: { start: number; end: number }[]
  bracket_results: BracketResult[]
  drift: Drift
  slice_files: string[]
  bank_dir: string
}

// ── Snippet Bank Index ──────────────────────────────────────

export interface BankEntry {
  run_id: string
  timestamp: string
  intent: string
  brackets: string[]
  compliance_verdict: ComplianceVerdict
  compliance_score: number
  drift_verdict: DriftVerdict
  drift_score: number
  original: string
  variant: string
  source?: AudioSource
}

// ── Vocabulary ──────────────────────────────────────────────

export interface KeywordEntry {
  count: number
  avg_deltas: FeatureDeltas
  std_deltas: FeatureDeltas
  pass_rate: number
  associated_intents: string[]
}

export interface VocabIndex {
  total_runs: number
  built_at: string
  keywords: Record<string, KeywordEntry>
}

export interface KeywordLookup {
  keyword: string
  found: boolean
  count: number
  pass_rate: number
  effects: string[]
  avg_deltas: FeatureDeltas
  std_deltas: FeatureDeltas
  associated_intents: string[]
}

// ── Sessions ────────────────────────────────────────────────

export interface Iteration {
  iteration: number
  timestamp: string
  variant_prompt: string
  run_id: string
  compliance_score: number
  compliance_verdict: ComplianceVerdict
  drift_score: number
  drift_verdict: DriftVerdict
  notes: string
  met_targets: boolean
}

export interface Session {
  session_id: string
  status: 'active' | 'max_iterations_reached' | 'accepted'
  created_at: string
  prompt: string
  brackets: string[]
  intent: string
  max_iterations: number
  target_compliance: number
  target_drift: number
  iterations: Iteration[]
  accepted_run: string | null
  accepted_at: string | null
  accept_notes?: string
}

// ── Listen Response ─────────────────────────────────────────

export interface ListenRegion {
  window: string
  start: number
  end: number
  features: AudioFeatures
}

export interface ListenResponse {
  file: string
  duration: number
  sample_rate: number
  features?: AudioFeatures
  regions?: ListenRegion[]
}
