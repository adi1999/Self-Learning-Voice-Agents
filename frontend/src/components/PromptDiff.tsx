import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'

interface Props {
  section: string
  before: string
  after: string
}

export default function PromptDiff({ section, before, after }: Props) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Diff: [{section}]</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="after">
          <TabsList>
            <TabsTrigger value="before">Before (Parent)</TabsTrigger>
            <TabsTrigger value="after">After (Mutated)</TabsTrigger>
            <TabsTrigger value="side-by-side">Side by Side</TabsTrigger>
          </TabsList>
          <TabsContent value="before">
            <ScrollArea className="h-48">
              <pre className="text-xs whitespace-pre-wrap bg-red-50 text-red-900 p-3 rounded-md">
                {before}
              </pre>
            </ScrollArea>
          </TabsContent>
          <TabsContent value="after">
            <ScrollArea className="h-48">
              <pre className="text-xs whitespace-pre-wrap bg-green-50 text-green-900 p-3 rounded-md">
                {after}
              </pre>
            </ScrollArea>
          </TabsContent>
          <TabsContent value="side-by-side">
            <div className="grid grid-cols-2 gap-3">
              <ScrollArea className="h-48">
                <pre className="text-xs whitespace-pre-wrap bg-red-50 text-red-900 p-3 rounded-md">
                  {before}
                </pre>
              </ScrollArea>
              <ScrollArea className="h-48">
                <pre className="text-xs whitespace-pre-wrap bg-green-50 text-green-900 p-3 rounded-md">
                  {after}
                </pre>
              </ScrollArea>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
