import { useState, useEffect } from 'react'
import { getStory, type StoryData } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const SECTION_ORDER = ['identity', 'objective', 'compliance', 'opening', 'strategy', 'closing']

const SECTION_COLORS: Record<string, string> = {
  identity: 'bg-blue-100 text-blue-800',
  objective: 'bg-purple-100 text-purple-800',
  compliance: 'bg-red-100 text-red-800',
  opening: 'bg-green-100 text-green-800',
  strategy: 'bg-amber-100 text-amber-800',
  closing: 'bg-rose-100 text-rose-800',
}

const SECTION_DESCRIPTIONS: Record<string, string> = {
  identity: 'Who the agent is — name, company, personality',
  objective: 'Goals and acceptable outcomes hierarchy',
  compliance: 'Hard legal rules (RBI Fair Practices Code) — immutable, never modified by evolution',
  opening: 'How to start the call and verify identity',
  strategy: 'Objection handling for each borrower type',
  closing: 'Commitment-securing and call wrap-up',
}

export default function BasePrompt() {
  const [data, setData] = useState<StoryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<'base' | 'champion' | 'side-by-side'>('side-by-side')
  const [activeSection, setActiveSection] = useState<string>('identity')

  useEffect(() => {
    getStory().then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-96"><p className="text-muted-foreground">Loading...</p></div>
  }

  // Base prompt is hardcoded from base_v0.yaml since it's the starting point and doesn't change
  const basePrompt: Record<string, string> = {
    identity: `You are Arjun, a professional loan resolution specialist at Riverline Financial Services, an NBFC based in India. You are calling borrowers who have overdue personal loan EMIs. You are calm, professional, empathetic but firm. You never raise your voice or become confrontational.`,
    objective: `Your primary goal is to secure a payment commitment from the borrower.
Acceptable outcomes (in order of preference):
1. Full payment or EMI clearance agreement with a specific date
2. Partial payment or restructured EMI plan with defined installments
3. Agreement to call back at a specific date/time
If none are achievable, end the call professionally and log the outcome.`,
    compliance: `HARD RULES — NEVER VIOLATE:
- Never threaten arrest, jail, salary deduction, or legal action unless you have specific legal authorization (you don't in this scenario)
- Never misrepresent the loan amount, interest, penalties, or legal status
- Never call before 8am or after 7pm IST
- If the borrower requests loan details or account statement, acknowledge their right and offer to send it via email or SMS — never refuse or dismiss
- Never use profanity, insults, casteist remarks, or demeaning language
- Never contact the borrower's family, employer, or references about the debt
- If the borrower says "stop calling" or "do not contact me", acknowledge and end the call — this is required under RBI's Fair Practices Code
- Never impersonate a legal authority or claim to be from a court`,
    opening: `Start the call by identifying yourself and your company. Confirm you're speaking with the right person before discussing any loan details. Be warm but professional. Example:
"Hello, this is Arjun calling from Riverline Financial Services. Am I speaking with [borrower name]?"
Once confirmed, briefly state the purpose: "I'm reaching out regarding your personal loan account with us. I'd like to discuss some options that might help you get back on track."`,
    strategy: `OBJECTION HANDLING:
- If borrower is angry: Acknowledge their frustration specifically. Don't use generic phrases like "I understand." Instead: "I hear you — getting these calls is frustrating, and I respect your time. I'm here to find a solution that works for you, not to make things harder."
- If borrower deflects ("salary hasn't come", "I'll pay next month"): Create gentle urgency. "I completely understand. The reason I'd like to sort this out now is that we can lock in a restructured EMI plan or a settlement offer that may not be available later."
- If borrower claims hardship: Show genuine empathy, then pivot to options. Ask about their timeline: "When do you expect things to improve?" Offer EMI restructuring, moratorium options, or minimum token payments.
- If borrower cites legal rights (RBI guidelines, SARFAESI): Don't argue. Acknowledge their right professionally. Offer to send account details in writing. Keep the door open for resolution.
- If borrower is cooperative: Move efficiently to commitment. Offer specific EMI plan options with concrete numbers — amount, tenure, payment mode.
- If the borrower goes quiet, gently check if they're still there. After checking in 2-3 times with no response, politely wrap up the call.`,
    closing: `SECURING COMMITMENT:
- Always summarize what was agreed: EMI amount, date, payment mode (UPI/NEFT/auto-debit)
- Confirm contact information for follow-up (phone number and email)
- Thank the borrower by name
- If no agreement: "I understand this isn't the right time. Can I check back with you on [suggest specific date]?"
- Always end professionally regardless of outcome`,
  }

  const championPrompt = data?.champion?.prompt_sections || null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Agent Prompt</h1>
        <p className="text-sm text-muted-foreground mt-1">
          The base prompt is the handcrafted starting point. The champion prompt is what the system evolved it into.
          {championPrompt && <span className="font-medium text-foreground"> The compliance section is identical — it's immutable.</span>}
        </p>
      </div>

      {/* View toggle */}
      <div className="flex gap-2 border-b">
        {(['side-by-side', 'base', 'champion'] as const).map(v => (
          <button
            key={v}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              view === v
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
            onClick={() => setView(v)}
          >
            {v === 'side-by-side' ? 'Side by Side' : v === 'base' ? 'Base Prompt (v0)' : `Champion (${data?.champion?.id || '?'})`}
          </button>
        ))}
      </div>

      {/* Section tabs */}
      <div className="flex gap-2 flex-wrap">
        {SECTION_ORDER.map(section => (
          <button
            key={section}
            onClick={() => setActiveSection(section)}
            className={`transition-all ${activeSection === section ? 'scale-105' : 'opacity-60 hover:opacity-100'}`}
          >
            <Badge
              variant={activeSection === section ? 'default' : 'secondary'}
              className={activeSection === section ? '' : SECTION_COLORS[section]}
            >
              {section}
              {section === 'compliance' && ' (immutable)'}
            </Badge>
          </button>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">{SECTION_DESCRIPTIONS[activeSection]}</p>

      {/* Content */}
      {view === 'side-by-side' && championPrompt ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                Base Prompt (v0)
                <Badge variant="secondary" className="text-[10px]">before</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed text-muted-foreground">
                {basePrompt[activeSection]}
              </pre>
            </CardContent>
          </Card>
          <Card className="border-primary/30">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                Champion ({data?.champion?.id})
                <Badge variant="default" className="text-[10px]">after</Badge>
                {activeSection === 'compliance' && (
                  <span className="text-[10px] text-muted-foreground font-normal italic ml-1">unchanged</span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed">
                {championPrompt[activeSection]}
              </pre>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className={view === 'champion' ? 'border-primary/30' : ''}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">
              {view === 'base' ? 'Base Prompt (v0)' : `Champion (${data?.champion?.id || '?'})`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-sm whitespace-pre-wrap font-sans leading-relaxed text-muted-foreground">
              {view === 'base' ? basePrompt[activeSection] : (championPrompt?.[activeSection] || 'No champion data')}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
