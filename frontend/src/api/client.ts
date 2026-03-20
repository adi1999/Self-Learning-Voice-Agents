const BASE = ''

async function request<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || res.statusText)
  }
  return res.json()
}

// Versions
export const getVersions = () => request<VersionSummary[]>('/api/versions/')
export const getVersion = (id: string) => request<AgentVersion>(`/api/versions/${id}`)
export const getChampion = () => request<AgentVersion>('/api/versions/champion')

// Conversations
export const getConversations = (params: Record<string, string>) => {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString()
  return request<ConversationSummary[]>(`/api/conversations/?${qs}`)
}
export const getConversation = (id: string) => request<Conversation>(`/api/conversations/${id}`)

// Evolution
export const getEvolutionRuns = () => request<EvolutionRun[]>('/api/evolution/runs/')
export const getEvolutionRun = (id: string) => request<EvolutionRun>(`/api/evolution/runs/${id}`)
export const startEvolution = (body: StartEvolutionBody) =>
  request<TaskResponse>('/api/evolution/runs/', { method: 'POST', body: JSON.stringify(body) })
export const cancelEvolution = (taskId: string) =>
  request<{ status: string }>(`/api/evolution/runs/${taskId}`, { method: 'DELETE' })

// Simulation
export const startSimulation = (body: SimulateBody) =>
  request<TaskResponse>('/api/simulation/', { method: 'POST', body: JSON.stringify(body) })

// Evaluation
export const evaluateConversation = (conversationId: string) =>
  request<Conversation>('/api/evaluation/', { method: 'POST', body: JSON.stringify({ conversation_id: conversationId }) })

// Voice
export const getVoiceStatus = () => request<VoiceStatus>('/api/voice/status')
export const startVoice = (versionId: string) =>
  request<VoiceStatus>('/api/voice/start', { method: 'POST', body: JSON.stringify({ version_id: versionId }) })
export const stopVoice = () => request<VoiceStatus>('/api/voice/stop', { method: 'POST' })
export const sendOffer = (sdp: string, type: string) =>
  request<{ sdp: string; type: string }>('/api/voice/offer', { method: 'POST', body: JSON.stringify({ sdp, type }) })

// Story
export const getStory = () => request<StoryData>('/api/story/')

// Playbook
export const getPlaybookTactics = () => request<StrategyTactic[]>('/api/playbook/tactics')
export const getPlaybookFailures = () => request<FailedApproachData[]>('/api/playbook/failures')
export const getPlaybookStats = () => request<PlaybookStats>('/api/playbook/stats')

// Config
export const getConfig = () => request<AppConfig>('/api/config/')

// --- Types ---

export interface VersionSummary {
  id: string
  generation: number
  status: string
  aggregate_score: number | null
  mutation_target: string | null
  parent_id: string | null
  run_id: string | null
}

export interface PersonaScores {
  per_persona: Record<string, MetricScores>
  aggregate: number
}

export interface MetricScores {
  goal_completion: number
  conversational_quality: number
  compliance: number
  response_consistency: number
  sentiment_shift: number
  weighted_total: number
}

export interface AgentVersion {
  id: string
  run_id: string | null
  parent_id: string | null
  generation: number
  prompt_sections: Record<string, string>
  mutation_target: string | null
  rationale: string | null
  failure_patterns: string[]
  scores: PersonaScores | null
  status: string
  created_at: string
}

export interface TurnAnnotation {
  turn_index: number
  issue_type: string
  description: string
}

export interface EvalResult {
  goal_completion: number
  conversational_quality: number
  compliance: number
  response_consistency: number
  sentiment_shift: number
  weighted_total: number
  turn_annotations: TurnAnnotation[]
  hallucinations_found: string[]
  tone_assessment: string
  consistency_issues: string[]
}

export interface Turn {
  index: number
  role: 'agent' | 'borrower'
  content: string
  timestamp: string | null
  annotations: TurnAnnotation[]
}

export interface Conversation {
  id: string
  agent_version_id: string
  persona_type: string | null
  source: string
  turns: Turn[]
  outcome: string
  duration_turns: number
  eval_result: EvalResult | null
  created_at: string
}

export interface ConversationSummary {
  id: string
  agent_version_id: string
  persona_type: string | null
  source: string
  outcome: string
  duration_turns: number
  weighted_total: number | null
  created_at: string
}

export interface EvolutionRun {
  id: string
  start_time: string
  end_time: string
  champion_id: string
  generations_completed: number
  final_score: number
  termination_reason: string
  generation_log: GenerationEntry[]
  all_version_ids: string[]
  versions?: AgentVersion[]
}

export interface GenerationEntry {
  generation: number
  champion_id: string
  score: number
  versions_tested: string[]
  mutation_target: string | null
  promoted: string | null
}

export interface TaskResponse {
  task_id: string
  status: string
}

export interface StartEvolutionBody {
  max_generations?: number
  threshold?: number
  conversations_per_persona?: number
  start_from_champion?: boolean
  resume_run_id?: string | null
}

export interface SimulateBody {
  version_id: string
  persona: string
  evaluate?: boolean
}

export interface VoiceStatus {
  running: boolean
  pid: number | null
  port: number
  message?: string
  ready?: boolean
}

export interface AppConfig {
  max_generations: number
  score_threshold: number
  conversations_per_persona: number
  persona_archetypes: string[]
  prompt_sections: string[]
  scoring_weights: Record<string, number>
  llm_provider: string
  simulation_model: string
  evaluation_model: string
  voice_model: string
}

export interface TurnReference {
  conversation_id: string
  turn_index: number
  content: string
}

export interface StrategyTactic {
  id: string
  persona_type: string
  prompt_section: string
  tactic: string
  example_turns: TurnReference[]
  score_impact: number
  source_version_id: string
  source_run_id: string | null
  created_at: string
}

export interface FailedApproachData {
  id: string
  target_section: string
  description: string
  failure_reason: string
  parent_version_id: string
  candidate_version_id: string
  score_before: number
  score_after: number
  persona_regressions: Record<string, number>
  source_run_id: string | null
  created_at: string
}

export interface PlaybookStats {
  total_tactics: number
  total_failures: number
  tactics_by_persona: Record<string, number>
  tactics_by_section: Record<string, number>
  failures_by_section: Record<string, number>
}

export interface StoryRunSummary {
  id: string
  generations_completed: number
  final_score: number
  termination_reason: string
  champion_id: string
}

export interface StoryData {
  run: {
    id: string
    generations_completed: number
    final_score: number
    termination_reason: string
    generation_log: Array<{
      generation: number
      champion_id: string
      score: number
      mutation_target: string | null
      promoted: string | null
    }>
  } | null
  all_runs: StoryRunSummary[]
  v0: {
    id: string
    score: number
    per_persona: Record<string, number>
  }
  champion: {
    id: string
    score: number
    per_persona: Record<string, number>
    mutation_target: string | null
    rationale: string | null
    prompt_sections: Record<string, string>
  }
  biggest_improvement: {
    persona: string
    before: number
    after: number
    delta: number
  }
  weakest_v0_persona: {
    persona: string
    score: number
  } | null
  top_tactics: Array<{
    persona_type: string
    prompt_section: string
    tactic: string
    score_impact: number
  }>
  playbook_stats: {
    total_tactics: number
    total_failures: number
  }
  total_conversations: number
  total_versions: number
}
