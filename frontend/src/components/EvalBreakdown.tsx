import type { EvalResult } from '@/api/client'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertTriangle, AlertCircle } from 'lucide-react'

interface Props {
  eval: EvalResult
}

const metrics = [
  { key: 'goal_completion', label: 'Goal Completion', max: 3 },
  { key: 'conversational_quality', label: 'Quality', max: 5 },
  { key: 'compliance', label: 'Compliance', max: 1 },
  { key: 'response_consistency', label: 'Consistency', max: 1 },
  { key: 'sentiment_shift', label: 'Sentiment', max: 1, min: -1 },
] as const

export default function EvalBreakdown({ eval: ev }: Props) {
  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            <TableHead className="text-right">Score</TableHead>
            <TableHead className="text-right">Range</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {metrics.map(m => (
            <TableRow key={m.key}>
              <TableCell>{m.label}</TableCell>
              <TableCell className="text-right font-mono">
                {(ev[m.key] as number).toFixed(2)}
              </TableCell>
              <TableCell className="text-right text-muted-foreground">
                {'min' in m ? `${m.min}–${m.max}` : `0–${m.max}`}
              </TableCell>
            </TableRow>
          ))}
          <TableRow className="bg-primary/5 font-medium">
            <TableCell className="text-primary">Weighted Total</TableCell>
            <TableCell className="text-right font-mono text-primary">
              {ev.weighted_total.toFixed(2)}
            </TableCell>
            <TableCell className="text-right text-primary/60">0–5</TableCell>
          </TableRow>
        </TableBody>
      </Table>

      {ev.hallucinations_found.length > 0 && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Hallucinations</AlertTitle>
          <AlertDescription>
            {ev.hallucinations_found.map((h, i) => (
              <p key={i}>• {h}</p>
            ))}
          </AlertDescription>
        </Alert>
      )}

      {ev.consistency_issues.length > 0 && (
        <Alert>
          <AlertTriangle className="size-4" />
          <AlertTitle>Consistency Issues</AlertTitle>
          <AlertDescription>
            {ev.consistency_issues.map((c, i) => (
              <p key={i}>• {c}</p>
            ))}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
