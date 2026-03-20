import { Flame, Ghost, Heart, Scale, Handshake, type LucideIcon } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface Props {
  archetype: string
  description: string
  onSimulate: () => void
  loading: boolean
}

const ARCHETYPE_CONFIG: Record<string, { icon: LucideIcon; border: string; bg: string; iconColor: string }> = {
  angry: { icon: Flame, border: 'border-red-200', bg: 'bg-red-50', iconColor: 'text-red-500' },
  evasive: { icon: Ghost, border: 'border-amber-200', bg: 'bg-amber-50', iconColor: 'text-amber-500' },
  hardship: { icon: Heart, border: 'border-purple-200', bg: 'bg-purple-50', iconColor: 'text-purple-500' },
  informed: { icon: Scale, border: 'border-blue-200', bg: 'bg-blue-50', iconColor: 'text-blue-500' },
  cooperative: { icon: Handshake, border: 'border-green-200', bg: 'bg-green-50', iconColor: 'text-green-500' },
}

export default function PersonaCard({ archetype, description, onSimulate, loading }: Props) {
  const config = ARCHETYPE_CONFIG[archetype] || { icon: Flame, border: 'border-border', bg: 'bg-muted', iconColor: 'text-muted-foreground' }
  const Icon = config.icon

  return (
    <Card className={`${config.border} ${config.bg}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Icon className={`size-4 ${config.iconColor}`} />
          <span className="capitalize">{archetype}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={onSimulate}
          disabled={loading}
        >
          {loading ? 'Running...' : 'Simulate'}
        </Button>
      </CardContent>
    </Card>
  )
}
