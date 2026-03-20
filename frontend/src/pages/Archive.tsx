import { useState, useEffect } from 'react'
import { getVersions, getVersion, type VersionSummary, type AgentVersion } from '@/api/client'
import PromptDiff from '@/components/PromptDiff'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export default function Archive() {
  const [versions, setVersions] = useState<VersionSummary[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<AgentVersion | null>(null)
  const [parentDetail, setParentDetail] = useState<AgentVersion | null>(null)

  useEffect(() => {
    getVersions().then(setVersions)
  }, [])

  const handleExpand = async (openValues: string[]) => {
    const id = openValues[0] || null
    if (id === expandedId) {
      setExpandedId(null)
      setDetail(null)
      setParentDetail(null)
      return
    }
    setExpandedId(id)
    if (!id) return
    try {
      const v = await getVersion(id)
      setDetail(v)
      if (v.parent_id) {
        const p = await getVersion(v.parent_id)
        setParentDetail(p)
      } else {
        setParentDetail(null)
      }
    } catch {
      setDetail(null)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Agent Version Archive</h2>

      {versions.length === 0 ? (
        <p className="text-sm text-muted-foreground">No versions found. Run evolution first.</p>
      ) : (
        <Accordion onValueChange={handleExpand}>
          {versions.map(v => (
            <AccordionItem key={v.id} value={v.id}>
              <AccordionTrigger className="px-4 py-3 text-sm hover:no-underline">
                <div className="flex items-center gap-3">
                  <Badge variant={
                    v.status === 'promoted' ? 'default' :
                    v.status === 'base' ? 'secondary' :
                    'outline'
                  }>
                    {v.status}
                  </Badge>
                  <span className="font-mono">{v.id}</span>
                  <span className="text-xs text-muted-foreground">Gen {v.generation}</span>
                  {v.mutation_target && (
                    <Badge variant="outline" className="text-purple-600 border-purple-200 bg-purple-50">
                      {v.mutation_target}
                    </Badge>
                  )}
                </div>
                <span className="font-mono ml-auto mr-2">
                  {v.aggregate_score !== null ? v.aggregate_score.toFixed(2) : 'N/A'}
                </span>
              </AccordionTrigger>
              <AccordionContent className="px-4 pb-4">
                {detail && expandedId === v.id && (
                  <div className="space-y-4">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-xs text-muted-foreground">Metadata</CardTitle>
                      </CardHeader>
                      <CardContent className="text-xs text-muted-foreground space-y-0.5">
                        {detail.parent_id && <p>Parent: {detail.parent_id}</p>}
                        {detail.rationale && <p>Rationale: {detail.rationale}</p>}
                        {detail.failure_patterns.length > 0 && (
                          <p>Failure patterns: {detail.failure_patterns.join(', ')}</p>
                        )}
                      </CardContent>
                    </Card>

                    <div>
                      <h4 className="text-xs font-medium text-muted-foreground mb-2">Prompt Sections</h4>
                      <Accordion>
                        {Object.entries(detail.prompt_sections).map(([section, content]) => (
                          <AccordionItem key={section} value={section}>
                            <AccordionTrigger className="text-xs font-medium py-2">
                              [{section}]
                            </AccordionTrigger>
                            <AccordionContent>
                              <pre className="text-xs whitespace-pre-wrap bg-muted p-3 rounded-md">
                                {content}
                              </pre>
                            </AccordionContent>
                          </AccordionItem>
                        ))}
                      </Accordion>
                    </div>

                    {detail.parent_id && detail.mutation_target && parentDetail && (
                      <PromptDiff
                        section={detail.mutation_target}
                        before={parentDetail.prompt_sections[detail.mutation_target] || ''}
                        after={detail.prompt_sections[detail.mutation_target] || ''}
                      />
                    )}

                    {detail.scores && (
                      <div>
                        <h4 className="text-xs font-medium text-muted-foreground mb-2">Per-Persona Scores</h4>
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Persona</TableHead>
                              <TableHead className="text-right">Goal</TableHead>
                              <TableHead className="text-right">Quality</TableHead>
                              <TableHead className="text-right">Compliance</TableHead>
                              <TableHead className="text-right">Consistency</TableHead>
                              <TableHead className="text-right">Sentiment</TableHead>
                              <TableHead className="text-right">Total</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {Object.entries(detail.scores.per_persona).map(([persona, ms]) => (
                              <TableRow key={persona}>
                                <TableCell className="capitalize font-medium">{persona}</TableCell>
                                <TableCell className="text-right font-mono">{ms.goal_completion.toFixed(1)}</TableCell>
                                <TableCell className="text-right font-mono">{ms.conversational_quality.toFixed(1)}</TableCell>
                                <TableCell className="text-right font-mono">{ms.compliance.toFixed(1)}</TableCell>
                                <TableCell className="text-right font-mono">{ms.response_consistency.toFixed(1)}</TableCell>
                                <TableCell className="text-right font-mono">{ms.sentiment_shift.toFixed(2)}</TableCell>
                                <TableCell className="text-right font-mono font-medium">{ms.weighted_total.toFixed(2)}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                          <TableFooter>
                            <TableRow>
                              <TableCell className="text-primary font-medium">Aggregate</TableCell>
                              <TableCell colSpan={5} />
                              <TableCell className="text-right font-mono text-primary font-medium">
                                {detail.scores.aggregate.toFixed(2)}
                              </TableCell>
                            </TableRow>
                          </TableFooter>
                        </Table>
                      </div>
                    )}
                  </div>
                )}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}
    </div>
  )
}
