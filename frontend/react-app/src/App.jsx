import { useState, useCallback } from 'react'
import TripForm from './components/TripForm'
import DecisionBanner from './components/DecisionBanner'
import RiskPanel from './components/RiskPanel'
import Timeline from './components/Timeline'
import ChatPanel from './components/ChatPanel'
import GateOverride from './components/GateOverride'

export default function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [lastRequest, setLastRequest] = useState(null)
  const [invalidated, setInvalidated] = useState(false)
  const [liveContext, setLiveContext] = useState({})

  // ── Submit a plan ──────────────────────────────────────────────
  const submitPlan = useCallback(async (formData) => {
    setLoading(true)
    setInvalidated(false)
    setLastRequest(formData)

    const isMulti = formData._multi === true
    const endpoint = isMulti ? '/api/plan-multi' : '/api/plan'
    // Strip internal flags before sending
    const { _multi, ...payload } = formData

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (res.ok) {
        const data = await res.json()
        setResult(data)
      } else {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
        setResult({
          decision: 'NO',
          risk_level: 'high',
          suggested_action: `Error: ${err.detail}`,
          reason: err.detail,
        })
      }
    } catch (e) {
      setResult({
        decision: 'NO',
        risk_level: 'high',
        suggested_action: 'Cannot reach the backend. Is FastAPI running on port 8000?',
        reason: e.message,
      })
    } finally {
      setLoading(false)
    }
  }, [])

  // ── Gate override → invalidate + re-plan ───────────────────────
  const handleGateOverride = useCallback(async (newGate) => {
    if (!lastRequest) return

    setInvalidated(true)
    const updated = { ...lastRequest, gate: newGate }
    setLastRequest(updated)

    await new Promise(r => setTimeout(r, 800))
    submitPlan(updated)
  }, [lastRequest, submitPlan])

  // ── Chat context ───────────────────────────────────────────────
  const chatContext = {
    gate: liveContext.gate || lastRequest?.gate,
    walking_speed: liveContext.walking_speed,
    itinerary_minutes: liveContext.itinerary_minutes,
    airline: liveContext.airline || lastRequest?.airline || null,
    experience: liveContext.experience || lastRequest?.experience || 'normal',
    decision: result?.decision,
    destination: lastRequest?.destination,
    risk_level: result?.risk_level,
    usable_time: result?.usable_time,
    required_minutes: result?.planner?.required_minutes,
    explanation: result?.explanation || '',
  }

  return (
    <div className="app-container">
      {/* ── Header ──────────────────────────────────── */}
      <header className="app-header">
        <div className="header-left">
          <div className="header-logo">✈️</div>
          <div>
            <h1>Delay2Decision</h1>
            <div className="subtitle">AI-Powered Layover Trip Planner · JFK Airport</div>
          </div>
        </div>
        <div className="status-badge">
          <span className="status-dot" />
          System Online
        </div>
      </header>

      {/* ── Invalidation Warner ───────────────────── */}
      {invalidated && (
        <div className="invalidation-banner">
          <span className="loading-spinner" />
          Gate changed — re-evaluating your trip plan...
        </div>
      )}

      {/* ── Dashboard Grid ────────────────────────── */}
      <div className="dashboard">
        <TripForm 
          onSubmit={submitPlan} 
          loading={loading} 
          syncData={lastRequest} 
          onLiveUpdate={setLiveContext} 
        />

        <DecisionBanner
          decision={result?.decision}
          action={result?.suggested_action}
          loading={loading}
        />

        <RiskPanel data={result} loading={loading} />

        <Timeline
          simulation={result?.simulation}
          itineraryMinutes={result?.itinerary_minutes}
          bufferMinutes={result?.buffer_minutes}
          usableTime={result?.usable_time}
          destination={lastRequest?.destination}
          legs={result?.legs}
          totalRequired={result?.total_required}
          loading={loading}
        />

        <ChatPanel 
          planContext={chatContext} 
          onPlanUpdate={(planResult) => {
            setResult(planResult)
            if (planResult.request_params) {
              setLastRequest(planResult.request_params)
            }
          }} 
        />
      </div>

      {/* ── Gate Override ─────────────────────────── */}
      {result && (
        <GateOverride
          currentGate={lastRequest?.gate || 'GATE_B1'}
          onOverride={handleGateOverride}
        />
      )}
    </div>
  )
}
