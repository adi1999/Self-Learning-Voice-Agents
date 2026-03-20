import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { GenerationEntry, AgentVersion } from '@/api/client'

interface Props {
  generationLog: GenerationEntry[]
  versions?: AgentVersion[]
}

const PERSONA_COLORS: Record<string, string> = {
  angry: '#ef4444',
  evasive: '#f59e0b',
  hardship: '#8b5cf6',
  informed: '#3b82f6',
  cooperative: '#10b981',
}

export default function ScoreChart({ generationLog, versions = [] }: Props) {
  const versionMap = Object.fromEntries(versions.map(v => [v.id, v]))

  const data = generationLog.map(entry => {
    const row: Record<string, unknown> = {
      generation: entry.generation,
      aggregate: entry.score,
    }
    const v = versionMap[entry.champion_id]
    if (v?.scores) {
      for (const [persona, scores] of Object.entries(v.scores.per_persona)) {
        row[persona] = scores.weighted_total
      }
    }
    return row
  })

  if (data.length < 2) return null

  const personas = versions.length > 0
    ? Object.keys(versions[0]?.scores?.per_persona || {})
    : []

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Score Evolution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="generation" label={{ value: 'Generation', position: 'bottom', offset: -5 }} />
            <YAxis domain={[0, 5]} label={{ value: 'Score', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            <Line
              type="monotone"
              dataKey="aggregate"
              stroke="hsl(var(--primary))"
              strokeWidth={3}
              name="Aggregate"
              dot={{ r: 4 }}
            />
            {personas.map(p => (
              <Line
                key={p}
                type="monotone"
                dataKey={p}
                stroke={PERSONA_COLORS[p] || '#9ca3af'}
                strokeWidth={1.5}
                name={p.charAt(0).toUpperCase() + p.slice(1)}
                strokeDasharray="4 2"
                dot={{ r: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
