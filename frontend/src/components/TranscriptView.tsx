import { Bot, User } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Turn } from '@/api/client'

interface Props {
  turns: Turn[]
}

export default function TranscriptView({ turns }: Props) {
  return (
    <ScrollArea className="h-[500px]">
      <div className="space-y-3 pr-4">
        {turns.map(turn => (
          <div
            key={turn.index}
            className={`flex gap-3 ${turn.role === 'agent' ? '' : 'flex-row-reverse'}`}
          >
            <div className="shrink-0 mt-1">
              {turn.role === 'agent' ? (
                <div className="size-7 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="size-4 text-primary" />
                </div>
              ) : (
                <div className="size-7 rounded-full bg-muted flex items-center justify-center">
                  <User className="size-4 text-muted-foreground" />
                </div>
              )}
            </div>
            <div
              className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${
                turn.role === 'agent'
                  ? 'bg-primary/5 border border-primary/10'
                  : 'bg-muted border border-border'
              }`}
            >
              <div className="text-xs font-medium mb-1 text-muted-foreground">
                {turn.role === 'agent' ? 'Agent' : 'Borrower'} · Turn {turn.index}
              </div>
              <p className="whitespace-pre-wrap">{turn.content}</p>
              {turn.annotations.length > 0 && (
                <div className="mt-2 space-y-1">
                  {turn.annotations.map((a, i) => (
                    <Badge key={i} variant="destructive" className="text-xs font-normal">
                      {a.issue_type}: {a.description}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {turns.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">No turns yet</p>
        )}
      </div>
    </ScrollArea>
  )
}
