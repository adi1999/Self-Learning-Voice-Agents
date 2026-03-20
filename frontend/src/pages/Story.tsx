import { useState, useEffect } from 'react'
import { getStory, type StoryData } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, LabelList,
} from 'recharts'
import { NavLink } from 'react-router-dom'
import {
  ArrowRight, TrendingUp, Brain, Target, Mic, CheckCircle2, Lightbulb,
  BarChart3, ChevronDown, ChevronUp, FileText,
} from 'lucide-react'

const PERSONA_COLORS: Record<string, string> = {
  angry: '#ef4444',
  evasive: '#f59e0b',
  hardship: '#8b5cf6',
  informed: '#3b82f6',
  cooperative: '#10b981',
}

const SECTION_COLORS: Record<string, string> = {
  identity: 'bg-blue-100 text-blue-800',
  objective: 'bg-purple-100 text-purple-800',
  opening: 'bg-green-100 text-green-800',
  strategy: 'bg-amber-100 text-amber-800',
  closing: 'bg-rose-100 text-rose-800',
}

const PERSONA_BADGE: Record<string, string> = {
  angry: 'bg-red-100 text-red-800',
  evasive: 'bg-slate-100 text-slate-800',
  hardship: 'bg-sky-100 text-sky-800',
  informed: 'bg-indigo-100 text-indigo-800',
  cooperative: 'bg-emerald-100 text-emerald-800',
}

const SECTION_ORDER = ['identity', 'objective', 'compliance', 'opening', 'strategy', 'closing']

export default function Story() {
  const [data, setData] = useState<StoryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [promptOpen, setPromptOpen] = useState(false)
  const [openSection, setOpenSection] = useState<string | null>(null)

  useEffect(() => {
    getStory().then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-muted-foreground">Loading evolution story...</p>
      </div>
    )
  }

  if (!data?.run) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <Brain className="size-12 text-muted-foreground/30" />
        <p className="text-muted-foreground">No evolution runs yet. Start one from the Evolution page.</p>
        <NavLink to="/evolution" className="text-primary underline text-sm">Go to Evolution</NavLink>
      </div>
    )
  }

  const { run, all_runs, v0, champion, biggest_improvement, weakest_v0_persona, top_tactics, playbook_stats, total_conversations, total_versions } = data

  const scoreData = run.generation_log.map(g => ({
    gen: `Gen ${g.generation}`,
    score: g.score,
    target: g.mutation_target,
  }))

  const personaData = Object.keys(v0.per_persona).map(p => ({
    persona: p.charAt(0).toUpperCase() + p.slice(1),
    key: p,
    before: v0.per_persona[p],
    after: champion.per_persona[p],
    delta: champion.per_persona[p] - v0.per_persona[p],
  })).sort((a, b) => b.delta - a.delta)

  const timeline = run.generation_log.filter(g => g.generation > 0).map(g => ({
    gen: g.generation,
    section: g.mutation_target || '—',
    promoted: !!g.promoted,
    score: g.score,
    prevScore: run.generation_log[g.generation - 1]?.score || v0.score,
  }))

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Hero */}
      <div className="text-center space-y-3 py-4">
        <h1 className="text-3xl font-bold tracking-tight">Evolution Story</h1>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          Across {all_runs.length} evolution run{all_runs.length > 1 ? 's' : ''} and {total_conversations} simulated conversations,
          the system improved the agent from{' '}
          <span className="font-semibold text-foreground">{v0.score.toFixed(2)}</span> to{' '}
          <span className="font-semibold text-foreground">{champion.score.toFixed(2)}</span> —
          evaluated against 5 borrower personas, scored by 5 LLM judges.
        </p>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold text-muted-foreground">{v0.score.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground mt-1">Starting Score</div>
          </CardContent>
        </Card>
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold text-primary">{champion.score.toFixed(2)}</div>
            <div className="text-xs text-muted-foreground mt-1">Final Score</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{all_runs.length}</div>
            <div className="text-xs text-muted-foreground mt-1">Evolution Runs</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{total_versions}</div>
            <div className="text-xs text-muted-foreground mt-1">Versions Tested</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <div className="text-3xl font-bold">{total_conversations}</div>
            <div className="text-xs text-muted-foreground mt-1">Conversations</div>
          </CardContent>
        </Card>
      </div>

      {/* All runs overview */}
      {all_runs.length > 1 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="size-4" />
              Evolution Runs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              {all_runs.map((r, i) => (
                <div key={r.id} className={`flex items-center justify-between p-3 rounded-lg ${i === 0 ? 'bg-primary/5 border border-primary/20' : 'bg-muted/50'}`}>
                  <div className="flex items-center gap-3">
                    {i === 0 && <Badge variant="default" className="text-[10px]">best</Badge>}
                    <span className="text-sm font-mono">{r.id}</span>
                    <span className="text-xs text-muted-foreground">{r.generations_completed} generations</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold">{r.final_score.toFixed(2)}</span>
                    <Badge variant="secondary" className="text-[10px]">{r.termination_reason.replace('_', ' ')}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Score progression */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="size-4" />
            Score Progression
            <span className="text-xs text-muted-foreground font-normal ml-2">(best run: {run.id})</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={scoreData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="gen" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 5]} tick={{ fontSize: 12 }} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0].payload
                  return (
                    <div className="bg-background border rounded-lg p-3 shadow-lg text-sm">
                      <p className="font-medium">{d.gen}: {d.score.toFixed(2)}</p>
                      {d.target && <p className="text-muted-foreground">Mutated: <span className="font-medium text-foreground">{d.target}</span></p>}
                    </div>
                  )
                }}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="hsl(var(--primary))"
                strokeWidth={3}
                dot={{ r: 6, fill: 'hsl(var(--primary))' }}
                activeDot={{ r: 8 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* What happened each generation */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Target className="size-4" />
            What Happened Each Generation
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
            <div className="flex-shrink-0 w-16 text-sm font-medium text-muted-foreground">Gen 0</div>
            <div className="flex-1">
              <p className="text-sm">Base prompt evaluated. Score: <span className="font-semibold">{v0.score.toFixed(2)}</span></p>
              {weakest_v0_persona && (
                <p className="text-xs text-muted-foreground mt-1">
                  Weakest persona: <span className="font-medium">{weakest_v0_persona.persona.charAt(0).toUpperCase() + weakest_v0_persona.persona.slice(1)}</span> ({weakest_v0_persona.score.toFixed(2)})
                </p>
              )}
            </div>
          </div>

          {timeline.map(t => {
            const delta = t.score - t.prevScore
            return (
              <div key={t.gen} className={`flex items-start gap-3 p-3 rounded-lg ${t.promoted ? 'bg-primary/5 border border-primary/20' : 'bg-muted/50'}`}>
                <div className="flex-shrink-0 w-16 text-sm font-medium text-muted-foreground">Gen {t.gen}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm">Mutated</span>
                    <Badge variant="secondary" className={SECTION_COLORS[t.section] || ''}>{t.section}</Badge>
                    <ArrowRight className="size-3 text-muted-foreground" />
                    <span className="text-sm font-semibold">{t.score.toFixed(2)}</span>
                    <span className={`text-xs ${delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-500' : 'text-muted-foreground'}`}>
                      ({delta > 0 ? '+' : ''}{delta.toFixed(2)})
                    </span>
                    {t.promoted ? (
                      <Badge variant="default" className="text-[10px] px-1.5 py-0">promoted</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">kept parent</span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      {/* Per-persona before/after */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <TrendingUp className="size-4" />
            Per-Persona Improvement
          </CardTitle>
          {biggest_improvement && (
            <p className="text-xs text-muted-foreground">
              Biggest gain: <span className="font-semibold">{biggest_improvement.persona.charAt(0).toUpperCase() + biggest_improvement.persona.slice(1)}</span>{' '}
              ({biggest_improvement.before.toFixed(2)} → {biggest_improvement.after.toFixed(2)}, +{biggest_improvement.delta.toFixed(2)})
            </p>
          )}
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={personaData} layout="vertical" margin={{ left: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis type="number" domain={[0, 5]} tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="persona" tick={{ fontSize: 12 }} width={80} />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const d = payload[0]?.payload
                  if (!d) return null
                  return (
                    <div className="bg-background border rounded-lg p-3 shadow-lg text-sm">
                      <p className="font-medium">{d.persona}</p>
                      <p className="text-muted-foreground">Before: {d.before.toFixed(2)} → After: {d.after.toFixed(2)}</p>
                      <p className={d.delta > 0 ? 'text-green-600' : 'text-red-500'}>
                        {d.delta > 0 ? '+' : ''}{d.delta.toFixed(2)}
                      </p>
                    </div>
                  )
                }}
              />
              <Bar dataKey="before" fill="hsl(var(--muted-foreground))" opacity={0.3} radius={[0, 4, 4, 0]} barSize={16} name="Before" />
              <Bar dataKey="after" radius={[0, 4, 4, 0]} barSize={16} name="After">
                {personaData.map(d => (
                  <Cell key={d.key} fill={PERSONA_COLORS[d.key] || '#9ca3af'} />
                ))}
                <LabelList dataKey="after" position="right" formatter={(v: number) => v.toFixed(2)} style={{ fontSize: 11 }} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* The Winning Mutation */}
      {champion.rationale && (
        <Card className="border-primary/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="size-4 text-primary" />
              The Winning Mutation
            </CardTitle>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-muted-foreground">Section mutated:</span>
              <Badge variant="secondary" className={SECTION_COLORS[champion.mutation_target || ''] || ''}>
                {champion.mutation_target}
              </Badge>
              <span className="text-xs text-muted-foreground">Champion:</span>
              <span className="text-xs font-mono">{champion.id}</span>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{champion.rationale}</p>
          </CardContent>
        </Card>
      )}

      {/* Champion Prompt */}
      {champion.prompt_sections && (
        <Card>
          <CardHeader
            className="cursor-pointer select-none"
            onClick={() => setPromptOpen(!promptOpen)}
          >
            <CardTitle className="flex items-center justify-between text-base">
              <div className="flex items-center gap-2">
                <FileText className="size-4" />
                Champion Prompt
                <span className="text-xs text-muted-foreground font-normal">({champion.id})</span>
              </div>
              {promptOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </CardTitle>
          </CardHeader>
          {promptOpen && (
            <CardContent className="space-y-2 pt-0">
              {SECTION_ORDER.map(section => {
                const text = champion.prompt_sections[section]
                if (!text) return null
                const isOpen = openSection === section
                return (
                  <div key={section} className="border rounded-lg overflow-hidden">
                    <button
                      className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors text-left"
                      onClick={(e) => { e.stopPropagation(); setOpenSection(isOpen ? null : section) }}
                    >
                      <Badge variant="secondary" className={SECTION_COLORS[section] || ''}>
                        {section}
                      </Badge>
                      {isOpen ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                    </button>
                    {isOpen && (
                      <div className="px-3 pb-3">
                        <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed text-muted-foreground bg-muted/30 rounded p-3">
                          {text}
                        </pre>
                      </div>
                    )}
                  </div>
                )
              })}
            </CardContent>
          )}
        </Card>
      )}

      {/* What the system learned */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Lightbulb className="size-4" />
            What the System Learned
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            {playbook_stats.total_tactics} tactics extracted, {playbook_stats.total_failures} failed approaches recorded across all runs.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {top_tactics.length === 0 ? (
            <p className="text-sm text-muted-foreground">No tactics extracted yet.</p>
          ) : (
            top_tactics.map((t, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50">
                <div className="flex-shrink-0 flex gap-1.5 pt-0.5">
                  <Badge variant="secondary" className={`text-[10px] ${PERSONA_BADGE[t.persona_type] || ''}`}>
                    {t.persona_type}
                  </Badge>
                  <Badge variant="secondary" className={`text-[10px] ${SECTION_COLORS[t.prompt_section] || ''}`}>
                    {t.prompt_section}
                  </Badge>
                </div>
                <p className="text-sm flex-1">{t.tactic}</p>
              </div>
            ))
          )}
          <NavLink to="/playbook" className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
            View full playbook <ArrowRight className="size-3" />
          </NavLink>
        </CardContent>
      </Card>

      <Separator />

      {/* Explore further */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pb-8">
        <NavLink to="/evolution">
          <Card className="hover:border-primary/40 transition-colors cursor-pointer h-full">
            <CardContent className="pt-6 text-center">
              <TrendingUp className="size-5 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm font-medium">Evolution Runs</p>
              <p className="text-xs text-muted-foreground">Start new runs</p>
            </CardContent>
          </Card>
        </NavLink>
        <NavLink to="/conversations">
          <Card className="hover:border-primary/40 transition-colors cursor-pointer h-full">
            <CardContent className="pt-6 text-center">
              <Brain className="size-5 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm font-medium">Conversations</p>
              <p className="text-xs text-muted-foreground">{total_conversations} transcripts</p>
            </CardContent>
          </Card>
        </NavLink>
        <NavLink to="/playbook">
          <Card className="hover:border-primary/40 transition-colors cursor-pointer h-full">
            <CardContent className="pt-6 text-center">
              <Lightbulb className="size-5 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm font-medium">Playbook</p>
              <p className="text-xs text-muted-foreground">{playbook_stats.total_tactics} tactics</p>
            </CardContent>
          </Card>
        </NavLink>
        <NavLink to="/voice">
          <Card className="hover:border-primary/40 transition-colors cursor-pointer h-full">
            <CardContent className="pt-6 text-center">
              <Mic className="size-5 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm font-medium">Voice Agent</p>
              <p className="text-xs text-muted-foreground">Talk to the agent</p>
            </CardContent>
          </Card>
        </NavLink>
      </div>
    </div>
  )
}
