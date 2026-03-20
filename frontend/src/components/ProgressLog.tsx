import { useEffect, useRef } from 'react'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'

interface LogEntry {
  generation?: number
  phase?: string
  message?: string
  score?: number
}

interface Props {
  entries: LogEntry[]
}

export default function ProgressLog({ entries }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries.length])

  return (
    <Card className="bg-slate-950 border-slate-800">
      <CardContent className="p-0">
        <ScrollArea className="h-64">
          <div className="p-3 font-mono text-xs space-y-0.5">
            {entries.map((e, i) => {
              const gen = e.generation ?? '?'
              const phase = e.phase ?? ''
              let line = `[Gen ${gen}] ${phase}`
              if (e.message) line += ` — ${e.message}`
              if (e.score != null) line += ` | Score: ${e.score.toFixed(2)}`

              const isDone = phase === 'done'
              const isError = phase === 'error'

              return (
                <div key={i} className={`flex items-center gap-1.5 py-0.5 ${
                  isDone ? 'text-green-400' : isError ? 'text-red-400' : 'text-slate-300'
                }`}>
                  {isDone ? <CheckCircle2 className="size-3 shrink-0" /> :
                   isError ? <XCircle className="size-3 shrink-0" /> :
                   <Loader2 className="size-3 shrink-0 animate-spin opacity-40" />}
                  {line}
                </div>
              )
            })}
            {entries.length === 0 && (
              <div className="text-slate-500">Waiting for events...</div>
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
