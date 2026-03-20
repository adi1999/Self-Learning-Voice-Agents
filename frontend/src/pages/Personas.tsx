import { useState, useEffect, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import { getVersions, getChampion, startSimulation, getConversation, getConversations, type Conversation, type Turn } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import PersonaCard from '@/components/PersonaCard'
import TranscriptView from '@/components/TranscriptView'
import EvalBreakdown from '@/components/EvalBreakdown'
import VersionSelector from '@/components/VersionSelector'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const PERSONA_DESCRIPTIONS: Record<string, string> = {
  angry: 'Hostile, questions legitimacy, threatens RBI complaint.',
  evasive: 'Dodges questions, never commits, polite but slippery.',
  hardship: 'Genuine financial difficulty, emotional, needs empathy.',
  informed: 'Knows RBI guidelines, cites SARFAESI, calm and methodical.',
  cooperative: 'Willing to pay, asks about EMI plans, easiest persona.',
}

const ARCHETYPES = ['angry', 'evasive', 'hardship', 'informed', 'cooperative']

export default function Personas() {
  const [selectedVersion, setSelectedVersion] = useState('')
  const [loading, setLoading] = useState<string | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [liveTurns, setLiveTurns] = useState<Turn[]>([])
  const [result, setResult] = useState<Conversation | null>(null)
  const [activePersona, setActivePersona] = useState<string | null>(null)

  const sseUrl = taskId ? `/api/simulation/${taskId}/stream` : null
  const { messages, done, connect } = useSSE(sseUrl)

  useEffect(() => {
    getChampion().then(c => setSelectedVersion(c.id)).catch(() => {
      getVersions().then(vs => {
        if (vs.length > 0) setSelectedVersion(vs[0].id)
      })
    })
  }, [])

  useEffect(() => {
    const turns: Turn[] = []
    for (const msg of messages) {
      if (msg.event === 'turn') {
        const d = msg.data as { turn_index: number; role: string; content: string }
        turns.push({
          index: d.turn_index,
          role: d.role as 'agent' | 'borrower',
          content: d.content,
          timestamp: null,
          annotations: [],
        })
      }
    }
    setLiveTurns(turns)
  }, [messages])

  useEffect(() => {
    if (done && taskId) {
      const timer = setTimeout(async () => {
        try {
          const convos = await getConversations({
            version_id: selectedVersion,
            persona_type: activePersona || '',
          })
          if (convos.length > 0) {
            const conv = await getConversation(convos[0].id)
            setResult(conv)
          }
        } catch {
          // ignore
        }
        setLoading(null)
      }, 1000)
      return () => clearTimeout(timer)
    }
  }, [done, taskId, selectedVersion, activePersona])

  const handleSimulate = useCallback(async (persona: string) => {
    if (!selectedVersion) return
    setLoading(persona)
    setActivePersona(persona)
    setLiveTurns([])
    setResult(null)
    setTaskId(null)

    try {
      const resp = await startSimulation({ version_id: selectedVersion, persona, evaluate: true })
      setTaskId(resp.task_id)
    } catch (err) {
      setLoading(null)
      alert(err instanceof Error ? err.message : 'Simulation failed')
    }
  }, [selectedVersion])

  useEffect(() => {
    if (taskId) {
      const t = setTimeout(() => connect(), 100)
      return () => clearTimeout(t)
    }
  }, [taskId, connect])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Test Personas</h2>
        <div className="w-72">
          <VersionSelector
            value={selectedVersion}
            onChange={setSelectedVersion}
            label=""
          />
        </div>
      </div>

      <div className="grid grid-cols-5 gap-3">
        {ARCHETYPES.map(a => (
          <PersonaCard
            key={a}
            archetype={a}
            description={PERSONA_DESCRIPTIONS[a]}
            onSimulate={() => handleSimulate(a)}
            loading={loading === a}
          />
        ))}
      </div>

      {(liveTurns.length > 0 || result) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              Results {activePersona && `— ${activePersona}`}
              {loading && (
                <Badge variant="secondary" className="gap-1">
                  <Loader2 className="size-3 animate-spin" /> Live
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="transcript">
              <TabsList>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="evaluation" disabled={!result?.eval_result}>
                  Evaluation
                </TabsTrigger>
              </TabsList>
              <TabsContent value="transcript" className="mt-3">
                <TranscriptView turns={result?.turns || liveTurns} />
              </TabsContent>
              <TabsContent value="evaluation" className="mt-3">
                {result?.eval_result ? (
                  <div>
                    <Badge variant="outline" className="mb-3">{result.outcome}</Badge>
                    <EvalBreakdown eval={result.eval_result} />
                  </div>
                ) : loading ? (
                  <div className="flex items-center justify-center h-32 text-sm text-muted-foreground">
                    Waiting for evaluation...
                  </div>
                ) : null}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
