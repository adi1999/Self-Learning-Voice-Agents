import { useState, useEffect, useRef, useCallback } from 'react'
import { Phone, PhoneOff, Loader2 } from 'lucide-react'
import { getVersions, getChampion, getVoiceStatus, startVoice, stopVoice, sendOffer, getConversations, type VoiceStatus, type ConversationSummary } from '@/api/client'
import VersionSelector from '@/components/VersionSelector'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'


export default function VoiceAgent() {
  const [selectedVersion, setSelectedVersion] = useState('')
  const [status, setStatus] = useState<VoiceStatus | null>(null)
  const [voiceConvos, setVoiceConvos] = useState<ConversationSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [callState, setCallState] = useState<'idle' | 'connecting' | 'active'>('idle')
  const [callError, setCallError] = useState<string | null>(null)

  const pcRef = useRef<RTCPeerConnection | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    getChampion().then(c => setSelectedVersion(c.id)).catch(() => {
      getVersions().then(vs => {
        if (vs.length > 0) setSelectedVersion(vs[0].id)
      })
    })
    getVoiceStatus().then(setStatus)
    getConversations({ source: 'voice_live' }).then(setVoiceConvos)
  }, [])

  const handleStartServer = async () => {
    if (!selectedVersion) return
    setLoading(true)
    try {
      const s = await startVoice(selectedVersion)
      setStatus(s)
      if (!s.ready) {
        setCallError('Voice server started but did not become ready. Check logs.')
      }
    } catch (err) {
      setCallError(err instanceof Error ? err.message : 'Failed to start')
    }
    setLoading(false)
  }

  const handleStopServer = async () => {
    setLoading(true)
    endCall()
    try {
      const s = await stopVoice()
      setStatus(s)
    } catch (err) {
      setCallError(err instanceof Error ? err.message : 'Failed to stop')
    }
    setLoading(false)
  }

  const startCall = useCallback(async () => {
    setCallState('connecting')
    setCallError(null)

    try {
      const localStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = localStream

      const pc = new RTCPeerConnection()
      pcRef.current = pc

      localStream.getTracks().forEach(track => pc.addTrack(track, localStream))

      pc.ontrack = (event) => {
        if (audioRef.current) {
          audioRef.current.srcObject = event.streams[0]
        }
      }

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
          endCall()
        }
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      await new Promise<void>((resolve) => {
        if (pc.iceGatheringState === 'complete') {
          resolve()
        } else {
          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === 'complete') resolve()
          }
        }
      })

      const answer = await sendOffer(
        pc.localDescription!.sdp,
        pc.localDescription!.type,
      )

      await pc.setRemoteDescription(new RTCSessionDescription({
        sdp: answer.sdp,
        type: answer.type as RTCSdpType,
      }))

      setCallState('active')
    } catch (err) {
      setCallError(err instanceof Error ? err.message : 'Connection failed')
      setCallState('idle')
      endCall()
    }
  }, [])

  const endCall = useCallback(() => {
    if (pcRef.current) {
      pcRef.current.close()
      pcRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    setCallState('idle')
    // Delay re-fetch: the pipeline saves the conversation AFTER transport
    // closes WebRTC, so give the server time to flush and persist.
    setTimeout(() => {
      getConversations({ source: 'voice_live' }).then(setVoiceConvos)
    }, 2000)
  }, [])

  const isRunning = status?.running ?? false

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Voice Agent</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Server Controls */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Voice Server</CardTitle>
              <Badge variant={isRunning ? 'default' : 'secondary'} className="gap-1.5">
                <span className={`size-2 rounded-full ${isRunning ? 'bg-green-400 animate-pulse' : 'bg-gray-400'}`} />
                {isRunning ? `Port ${status?.port}` : 'Stopped'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <VersionSelector
              value={selectedVersion}
              onChange={setSelectedVersion}
              disabled={isRunning}
            />
            <div className="flex gap-2">
              {!isRunning ? (
                <Button onClick={handleStartServer} disabled={loading} className="w-full">
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  Start Voice Server
                </Button>
              ) : (
                <Button variant="destructive" onClick={handleStopServer} disabled={loading} className="w-full">
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  Stop Voice Server
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Call Controls */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">WebRTC Call</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <audio ref={audioRef} autoPlay />

            {!isRunning ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                Start the voice server to make calls.
              </p>
            ) : (
              <div className="flex flex-col items-center gap-4 py-2">
                {callState === 'idle' && (
                  <Button size="lg" className="rounded-full gap-2 px-8" onClick={startCall}>
                    <Phone className="size-5" /> Start Call
                  </Button>
                )}
                {callState === 'connecting' && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" /> Connecting...
                  </div>
                )}
                {callState === 'active' && (
                  <div className="flex flex-col items-center gap-3">
                    <Badge variant="default" className="gap-1.5">
                      <span className="size-2 rounded-full bg-green-400 animate-pulse" />
                      Connected — speak now
                    </Badge>
                    <Button variant="destructive" size="lg" className="rounded-full gap-2 px-8" onClick={endCall}>
                      <PhoneOff className="size-5" /> End Call
                    </Button>
                  </div>
                )}
              </div>
            )}

            {callError && (
              <Alert variant="destructive">
                <AlertDescription>{callError}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Voice Conversation History */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">Voice Conversation History</h3>
        {voiceConvos.length === 0 ? (
          <p className="text-sm text-muted-foreground">No voice conversations yet.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead className="text-right">Turns</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead className="text-right">Score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {voiceConvos.map(c => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{c.id}</TableCell>
                  <TableCell className="text-right">{c.duration_turns}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{c.outcome}</Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono">
                    {c.weighted_total !== null ? c.weighted_total.toFixed(2) : 'N/A'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  )
}
