import type {
  AnalysisRun,
  BankEntry,
  KeywordLookup,
  ListenResponse,
  Session,
  VocabIndex,
} from './types'

// ── Helpers ─────────────────────────────────────────────────

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// ── Health ──────────────────────────────────────────────────

export async function healthCheck() {
  return get<{ status: string }>('/health')
}

// ── Listen ──────────────────────────────────────────────────

export async function listen(audioPath: string, regions?: string[]) {
  const params = new URLSearchParams({ audio: audioPath })
  regions?.forEach((r) => params.append('region', r))
  return get<ListenResponse>(`/listen?${params}`)
}

// ── Analyze ─────────────────────────────────────────────────

export async function analyze(opts: {
  original: string
  variant: string
  brackets: string[]
  intent: string
  prompt_text?: string
  source?: string
  save?: boolean
}) {
  return post<AnalysisRun>('/analyze', opts)
}

// ── Search / Snippet Bank ───────────────────────────────────

export async function searchBank(query: string) {
  return get<{ query: string; count: number; results: BankEntry[] }>(
    `/search?q=${encodeURIComponent(query)}`
  )
}

export async function listAllRuns() {
  return get<{ count: number; runs: BankEntry[] }>('/search?all=1')
}

export async function getRun(runId: string) {
  return get<{ run: AnalysisRun }>(`/search?run_id=${encodeURIComponent(runId)}`)
}

// ── Vocabulary ──────────────────────────────────────────────

export async function getVocab() {
  return get<VocabIndex>('/vocab')
}

export async function buildVocab() {
  return get<{ action: string; keywords: number; total_observations: number }>(
    '/vocab?action=build'
  )
}

export async function lookupKeyword(keyword: string) {
  return get<KeywordLookup>(
    `/vocab?action=lookup&keyword=${encodeURIComponent(keyword)}`
  )
}

export async function findKeywordsForFeature(
  feature: string,
  direction?: string
) {
  const params = new URLSearchParams({ action: 'find', feature })
  if (direction) params.set('direction', direction)
  return get<{
    feature: string
    direction: string | null
    matches: {
      keyword: string
      avg_delta: number
      std_delta: number
      count: number
      pass_rate: number
    }[]
  }>(`/vocab?${params}`)
}

// ── Sessions ────────────────────────────────────────────────

export async function listSessions() {
  return get<{ sessions: Session[] }>('/session')
}

export async function getSession(sessionId: string) {
  return get<Session>(`/session/${sessionId}`)
}

export async function initSession(opts: {
  prompt: string
  brackets: string[]
  intent: string
  max_iterations?: number
  target_compliance?: number
  target_drift?: number
}) {
  return post<Session>('/session/init', opts)
}

export async function recordIteration(opts: {
  session_id: string
  variant_prompt: string
  run_id: string
  compliance_score: number
  compliance_verdict: string
  drift_score: number
  drift_verdict: string
  notes?: string
}) {
  return post<{
    session_id: string
    iteration: number
    met_targets: boolean
    remaining: number
    status: string
  }>('/session/record', opts)
}

export async function acceptRun(opts: {
  session_id: string
  accepted_run: string
  notes?: string
}) {
  return post<{ session_id: string; status: string; accepted_run: string }>(
    '/session/accept',
    opts
  )
}

// ── Audio Proxy ─────────────────────────────────────────────

/** Returns a URL the browser can use to load audio via the bridge server. */
export function audioUrl(filePath: string): string {
  return `/audio?path=${encodeURIComponent(filePath)}`
}
