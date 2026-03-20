import { useState, useEffect } from 'react'
import {
  getPlaybookTactics,
  getPlaybookFailures,
  getPlaybookStats,
  type StrategyTactic,
  type FailedApproachData,
  type PlaybookStats,
} from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

const SECTION_COLORS: Record<string, string> = {
  identity: 'bg-blue-100 text-blue-800',
  objective: 'bg-purple-100 text-purple-800',
  opening: 'bg-green-100 text-green-800',
  strategy: 'bg-amber-100 text-amber-800',
  closing: 'bg-rose-100 text-rose-800',
}

const PERSONA_COLORS: Record<string, string> = {
  angry: 'bg-red-100 text-red-800',
  evasive: 'bg-slate-100 text-slate-800',
  hardship: 'bg-sky-100 text-sky-800',
  informed: 'bg-indigo-100 text-indigo-800',
  cooperative: 'bg-emerald-100 text-emerald-800',
}

const REASON_LABELS: Record<string, string> = {
  no_improvement: 'No Improvement',
  regression: 'Regression',
  not_selected: 'Not Selected',
}

export default function Playbook() {
  const [tactics, setTactics] = useState<StrategyTactic[]>([])
  const [failures, setFailures] = useState<FailedApproachData[]>([])
  const [stats, setStats] = useState<PlaybookStats | null>(null)
  const [tab, setTab] = useState<'tactics' | 'failures'>('tactics')

  useEffect(() => {
    getPlaybookTactics().then(setTactics)
    getPlaybookFailures().then(setFailures)
    getPlaybookStats().then(setStats)
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Strategy Playbook</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Accumulated knowledge from evolution runs — tactics that worked and approaches that failed.
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Tactics</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{stats.total_tactics}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Failed Approaches</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{stats.total_failures}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Personas Covered</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{Object.keys(stats.tactics_by_persona).length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Sections Covered</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{Object.keys(stats.tactics_by_section).length}</p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="flex gap-2 border-b">
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'tactics'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setTab('tactics')}
        >
          Winning Tactics ({tactics.length})
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'failures'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setTab('failures')}
        >
          Failed Approaches ({failures.length})
        </button>
      </div>

      {tab === 'tactics' && (
        <Card>
          <CardContent className="p-0">
            {tactics.length === 0 ? (
              <p className="p-6 text-sm text-muted-foreground">
                No tactics extracted yet. Run an evolution loop to start accumulating knowledge.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">Persona</TableHead>
                    <TableHead className="w-24">Section</TableHead>
                    <TableHead>Tactic</TableHead>
                    <TableHead className="w-20 text-right">Score</TableHead>
                    <TableHead className="w-28">Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tactics.map(t => (
                    <TableRow key={t.id}>
                      <TableCell>
                        <Badge variant="secondary" className={PERSONA_COLORS[t.persona_type] || ''}>
                          {t.persona_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={SECTION_COLORS[t.prompt_section] || ''}>
                          {t.prompt_section}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">{t.tactic}</TableCell>
                      <TableCell className="text-right font-mono text-sm">
                        {t.score_impact.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground font-mono">
                        {t.source_version_id}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'failures' && (
        <Card>
          <CardContent className="p-0">
            {failures.length === 0 ? (
              <p className="p-6 text-sm text-muted-foreground">
                No failed approaches recorded yet. Run an evolution loop to start tracking what doesn't work.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">Section</TableHead>
                    <TableHead>What Was Tried</TableHead>
                    <TableHead className="w-28">Reason</TableHead>
                    <TableHead className="w-32 text-right">Score Delta</TableHead>
                    <TableHead className="w-28">Regressions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {failures.map(f => {
                    const delta = f.score_after - f.score_before
                    return (
                      <TableRow key={f.id}>
                        <TableCell>
                          <Badge variant="secondary" className={SECTION_COLORS[f.target_section] || ''}>
                            {f.target_section}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm max-w-md truncate">{f.description}</TableCell>
                        <TableCell>
                          <Badge variant={f.failure_reason === 'regression' ? 'destructive' : 'secondary'}>
                            {REASON_LABELS[f.failure_reason] || f.failure_reason}
                          </Badge>
                        </TableCell>
                        <TableCell className={`text-right font-mono text-sm ${delta < 0 ? 'text-red-600' : 'text-muted-foreground'}`}>
                          {f.score_before.toFixed(2)} → {f.score_after.toFixed(2)}
                        </TableCell>
                        <TableCell className="text-xs">
                          {Object.keys(f.persona_regressions).length > 0
                            ? Object.entries(f.persona_regressions).map(([p, d]) => (
                                <span key={p} className="text-red-600 mr-1">
                                  {p}: {d.toFixed(2)}
                                </span>
                              ))
                            : <span className="text-muted-foreground">none</span>
                          }
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
