import { useState, useEffect, useCallback, Fragment } from 'react'
import { getConversations, getConversation, getVersions, evaluateConversation, type ConversationSummary, type Conversation, type VersionSummary } from '@/api/client'
import TranscriptView from '@/components/TranscriptView'
import EvalBreakdown from '@/components/EvalBreakdown'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const ARCHETYPES = ['angry', 'evasive', 'hardship', 'informed', 'cooperative']
const SOURCES = ['simulation', 'voice_live']
const OUTCOMES = ['success', 'rejection', 'hallucination', 'timeout', 'ended_by_user']

const ALL_VALUE = '__all__'

export default function Conversations() {
  const [versions, setVersions] = useState<VersionSummary[]>([])
  const [convos, setConvos] = useState<ConversationSummary[]>([])
  const [filters, setFilters] = useState({ version_id: '', persona_type: '', source: '', outcome: '' })
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [expandedConvo, setExpandedConvo] = useState<Conversation | null>(null)
  const [evaluating, setEvaluating] = useState<string | null>(null)

  useEffect(() => {
    getVersions().then(setVersions)
  }, [])

  const fetchConvos = useCallback(() => {
    getConversations(filters).then(setConvos)
  }, [filters])

  useEffect(() => { fetchConvos() }, [fetchConvos])

  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null)
      setExpandedConvo(null)
      return
    }
    setExpandedId(id)
    try {
      const c = await getConversation(id)
      setExpandedConvo(c)
    } catch {
      setExpandedConvo(null)
    }
  }

  const handleEvaluate = async (id: string) => {
    setEvaluating(id)
    try {
      const c = await evaluateConversation(id)
      setExpandedConvo(c)
      fetchConvos()
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Evaluation failed')
    }
    setEvaluating(null)
  }

  const updateFilter = (key: string, value: string | null) => {
    setFilters(prev => ({ ...prev, [key]: !value || value === ALL_VALUE ? '' : value }))
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Conversation Logs</h2>

      <div className="grid grid-cols-4 gap-3">
        <div className="space-y-1.5">
          <Label>Version</Label>
          <Select value={filters.version_id || ALL_VALUE} onValueChange={v => updateFilter('version_id', v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {versions.map(v => <SelectItem key={v.id} value={v.id}>{v.id}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Persona</Label>
          <Select value={filters.persona_type || ALL_VALUE} onValueChange={v => updateFilter('persona_type', v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {ARCHETYPES.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Source</Label>
          <Select value={filters.source || ALL_VALUE} onValueChange={v => updateFilter('source', v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {SOURCES.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Outcome</Label>
          <Select value={filters.outcome || ALL_VALUE} onValueChange={v => updateFilter('outcome', v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_VALUE}>All</SelectItem>
              {OUTCOMES.map(o => <SelectItem key={o} value={o}>{o}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">{convos.length} conversations found</p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>ID</TableHead>
            <TableHead>Persona</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Outcome</TableHead>
            <TableHead className="text-right">Turns</TableHead>
            <TableHead className="text-right">Score</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {convos.map(c => (
            <Fragment key={c.id}>
              <TableRow onClick={() => handleExpand(c.id)} className="cursor-pointer">
                <TableCell className="font-mono text-xs text-muted-foreground">{c.id}</TableCell>
                <TableCell className="capitalize">{c.persona_type || 'live'}</TableCell>
                <TableCell>{c.source}</TableCell>
                <TableCell>
                  <Badge variant={
                    c.outcome === 'success' ? 'default' :
                    c.outcome === 'rejection' ? 'destructive' :
                    'secondary'
                  }>
                    {c.outcome}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">{c.duration_turns}</TableCell>
                <TableCell className="text-right font-mono">
                  {c.weighted_total !== null ? c.weighted_total.toFixed(2) : 'N/A'}
                </TableCell>
              </TableRow>
              {expandedId === c.id && expandedConvo && (
                <TableRow>
                  <TableCell colSpan={6} className="p-4 bg-muted/30">
                    <div className="grid grid-cols-2 gap-4">
                      <TranscriptView turns={expandedConvo.turns} />
                      <div>
                        {expandedConvo.eval_result ? (
                          <EvalBreakdown eval={expandedConvo.eval_result} />
                        ) : (
                          <Button onClick={() => handleEvaluate(c.id)} disabled={evaluating === c.id}>
                            {evaluating === c.id ? 'Evaluating...' : 'Evaluate'}
                          </Button>
                        )}
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </Fragment>
          ))}
          {convos.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                No conversations found
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
