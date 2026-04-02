import { useState, useRef, useEffect } from 'react'

export default function ChatPanel({ planContext, onPlanUpdate }) {
  const [messages, setMessages] = useState([
    { role: 'bot', text: '👋 Hi! I\'m your JFK Airport layover assistant. Submit a trip plan, then ask me anything — why a decision was made, alternative routes, or safety tips!' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setLoading(true)

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg,
          context: planContext || null,
        }),
      })

      if (res.ok) {
        const data = await res.json()
        setMessages(prev => [...prev, { role: 'bot', text: data.reply }])

        // If the chat triggered a feasibility check, update the main UI
        if (data.plan_result && onPlanUpdate) {
          onPlanUpdate(data.plan_result)
        }
      } else {
        setMessages(prev => [...prev, { role: 'bot', text: '❌ Something went wrong. Please try again.' }])
      }
    } catch {
      setMessages(prev => [...prev, { role: 'bot', text: '🔌 Cannot reach the backend. Is FastAPI running on port 8000?' }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="glass-card chat-area chat-panel" id="chat-panel">
      <div className="section-title">AI Assistant</div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg ${msg.role}`}>
            {msg.text}
          </div>
        ))}
        {loading && (
          <div className="chat-msg bot" style={{ opacity: 0.7 }}>
            <span className="loading-spinner" />
            Thinking...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <input
          type="text"
          id="chat-input"
          placeholder="e.g. Why was my trip rejected?"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        <button onClick={sendMessage} disabled={loading} id="chat-send">
          Send →
        </button>
      </div>
    </div>
  )
}
