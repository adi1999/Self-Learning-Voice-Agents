import { useEffect, useState } from 'react'
import { Star, Crown } from 'lucide-react'
import { getVersions, type VersionSummary } from '@/api/client'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  SelectGroup,
  SelectLabel,
  SelectSeparator,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'

interface Props {
  value: string
  onChange: (id: string) => void
  label?: string
  disabled?: boolean
}

export default function VersionSelector({ value, onChange, label = 'Agent Version', disabled }: Props) {
  const [versions, setVersions] = useState<VersionSummary[]>([])

  useEffect(() => {
    getVersions().then(setVersions).catch(() => {})
  }, [])

  const promoted = versions.filter(v => v.status === 'promoted')
  const others = versions.filter(v => v.status !== 'promoted')

  return (
    <div className="space-y-1.5">
      {label && <Label>{label}</Label>}
      <Select value={value} onValueChange={v => { if (v) onChange(v) }} disabled={disabled}>
        <SelectTrigger>
          <SelectValue placeholder="Select version" />
        </SelectTrigger>
        <SelectContent>
          {promoted.length > 0 && (
            <SelectGroup>
              <SelectLabel>Champion</SelectLabel>
              {promoted.map(v => (
                <VersionOption key={v.id} version={v} />
              ))}
            </SelectGroup>
          )}
          {promoted.length > 0 && others.length > 0 && <SelectSeparator />}
          {others.length > 0 && (
            <SelectGroup>
              {promoted.length > 0 && <SelectLabel>Other versions</SelectLabel>}
              {others.map(v => (
                <VersionOption key={v.id} version={v} />
              ))}
            </SelectGroup>
          )}
        </SelectContent>
      </Select>
    </div>
  )
}

function VersionOption({ version: v }: { version: VersionSummary }) {
  return (
    <SelectItem value={v.id}>
      <span className="flex items-center gap-2">
        {v.status === 'promoted' && <Crown className="size-3.5 text-amber-500" />}
        <span className="font-mono text-xs">{v.id}</span>
        <span className="text-muted-foreground text-xs">gen {v.generation}</span>
        {v.aggregate_score !== null && (
          <span className="ml-auto tabular-nums font-medium text-xs">{v.aggregate_score.toFixed(2)}</span>
        )}
        {v.status === 'promoted' && <Star className="size-3 fill-amber-400 text-amber-400" />}
      </span>
    </SelectItem>
  )
}
