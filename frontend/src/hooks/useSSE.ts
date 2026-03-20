import { useEffect, useRef, useState, useCallback } from 'react'

interface SSEMessage {
  event: string
  data: unknown
}

export function useSSE(url: string | null) {
  const [messages, setMessages] = useState<SSEMessage[]>([])
  const [connected, setConnected] = useState(false)
  const [done, setDone] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  const connect = useCallback(() => {
    if (!url) return
    setMessages([])
    setDone(false)

    const es = new EventSource(url)
    esRef.current = es

    es.onopen = () => setConnected(true)
    es.onerror = () => {
      setConnected(false)
      es.close()
    }

    const handler = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        setMessages(prev => [...prev, { event: e.type, data }])
        if (e.type === 'done' || e.type === 'complete' || e.type === 'error') {
          setDone(true)
          setConnected(false)
          es.close()
        }
      } catch {
        // ignore parse errors
      }
    }

    es.addEventListener('progress', handler)
    es.addEventListener('turn', handler)
    es.addEventListener('complete', handler)
    es.addEventListener('done', handler)
    es.addEventListener('error', handler)
    es.addEventListener('cancelled', handler)
  }, [url])

  useEffect(() => {
    return () => {
      esRef.current?.close()
    }
  }, [])

  const close = useCallback(() => {
    esRef.current?.close()
    setConnected(false)
  }, [])

  return { messages, connected, done, connect, close }
}
