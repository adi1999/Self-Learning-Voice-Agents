import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { getEvolutionRuns, startEvolution, cancelEvolution, getEvolutionRun, type EvolutionRun, type TaskResponse } from '@/api/client'
import { useSSE } from '@/hooks/useSSE'
import ScoreChart from '@/components/ScoreChart'
import ProgressLog from '@/components/ProgressLog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export default function Evolution() {
  const [runs, setRuns] = useState<EvolutionRun[]>([])
  const [maxGen, setMaxGen] = useState(5)
  const [threshold, setThreshold] = useState(4.0)
  const [convosPerPersona, setConvosPerPersona] = useState(2)
  const [startFromChampion, setStartFromChampion] = useState(true)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [logEntries, setLogEntries] = useState<Array<{ generation?: number; phase?: string; message?: string; score?: number }>>([])
  const [expandedRun, setExpandedRun] = useState<string | null>(null)
  const [expandedDetail, setExpandedDetail] = useState<EvolutionRun | null>(null)

  const sseUrl = taskId ? `/api/evolution/runs/${taskId}/stream` : null
  const { messages, done, connect } = useSSE(sseUrl)

  useEffect(() => {
    getEvolutionRuns().then(setRuns)
  }, [])

  useEffect(() => {
    const entries = messages
      .filter(m => m.event === 'progress')
      .map(m => m.data as { generation?: number; phase?: string; message?: string; score?: number })
    setLogEntries(entries)
  }, [messages])

  useEffect(() => {
    if (done) {
      getEvolutionRuns().then(setRuns)
      setTaskId(null)
    }
  }, [done])

  const handleStart = async () => {
    setLogEntries([])
    try {
      const resp: TaskResponse = await startEvolution({
        max_generations: maxGen,
        threshold,
        conversations_per_persona: convosPerPersona,
        start_from_champion: startFromChampion,
      })
      setTaskId(resp.task_id)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to start')
    }
  }

  useEffect(() => {
    if (taskId) {
      const t = setTimeout(() => connect(), 100)
      return () => clearTimeout(t)
    }
  }, [taskId, connect])

  const handleCancel = async () => {
    if (taskId) {
      await cancelEvolution(taskId).catch(() => {})
    }
  }

  const handleExpand = async (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null)
      setExpandedDetail(null)
      return
    }
    setExpandedRun(runId)
    try {
      const detail = await getEvolutionRun(runId)
      setExpandedDetail(detail)
    } catch {
      setExpandedDetail(null)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Evolution Dashboard</h2>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Start New Evolution Run</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="space-y-1.5">
              <Label>Max Generations</Label>
              <Input type="number" value={maxGen} onChange={e => setMaxGen(+e.target.value)} min={1} max={20} />
            </div>
            <div className="space-y-1.5">
              <Label>Score Threshold</Label>
              <Input type="number" value={threshold} onChange={e => setThreshold(+e.target.value)} min={1} max={5} step={0.1} />
            </div>
            <div className="space-y-1.5">
              <Label>Convos/Persona</Label>
              <Input type="number" value={convosPerPersona} onChange={e => setConvosPerPersona(+e.target.value)} min={1} max={10} />
            </div>
            <div className="space-y-1.5">
              <Label>Start From</Label>
              <Select value={startFromChampion ? 'champion' : 'base'} onValueChange={v => { if (v) setStartFromChampion(v === 'champion') }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="champion">Champion</SelectItem>
                  <SelectItem value="base">Base Prompt</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleStart} disabled={!!taskId}>
              {taskId ? 'Running...' : 'Start Evolution'}
            </Button>
            {taskId && (
              <Button variant="destructive" onClick={handleCancel}>
                Cancel
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {logEntries.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-muted-foreground">Progress</h3>
          <ProgressLog entries={logEntries} />
        </div>
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">Run History</h3>
        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No evolution runs yet.</p>
        ) : (
          <div className="space-y-2">
            {runs.map(run => (
              <Collapsible
                key={run.id}
                open={expandedRun === run.id}
                onOpenChange={() => handleExpand(run.id)}
              >
                <Card>
                  <CollapsibleTrigger className="w-full">
                    <div className="flex items-center justify-between px-4 py-3 text-sm text-left">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-muted-foreground">{run.id}</span>
                        <Badge variant={
                          run.termination_reason === 'threshold_reached' ? 'default' :
                          run.termination_reason === 'in_progress' ? 'secondary' :
                          'outline'
                        }>
                          {run.termination_reason}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>{run.generations_completed} gens</span>
                        <span>Champion: {run.champion_id}</span>
                        <span className="font-mono font-medium text-foreground">{run.final_score.toFixed(2)}</span>
                        {expandedRun === run.id ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                      </div>
                    </div>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    {expandedDetail && (
                      <div className="border-t p-4 space-y-4">
                        <div>
                          <h4 className="text-xs font-medium text-muted-foreground mb-2">Generation Log</h4>
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Gen</TableHead>
                                <TableHead>Score</TableHead>
                                <TableHead>Mutation</TableHead>
                                <TableHead>Promoted</TableHead>
                                <TableHead>Tested</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {expandedDetail.generation_log.map(entry => (
                                <TableRow key={entry.generation}>
                                  <TableCell className="font-mono">{entry.generation}</TableCell>
                                  <TableCell className="font-mono">{entry.score.toFixed(2)}</TableCell>
                                  <TableCell>
                                    {entry.mutation_target && (
                                      <Badge variant="outline">{entry.mutation_target}</Badge>
                                    )}
                                  </TableCell>
                                  <TableCell className="font-mono text-xs">{entry.promoted || '—'}</TableCell>
                                  <TableCell className="font-mono text-xs">{entry.versions_tested.join(', ')}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                        <ScoreChart
                          generationLog={expandedDetail.generation_log}
                          versions={expandedDetail.versions}
                        />
                      </div>
                    )}
                  </CollapsibleContent>
                </Card>
              </Collapsible>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
