import { useState, useEffect } from 'react'
import CustomSelect from './CustomSelect'

const GATES = [
  'GATE_B1', 'GATE_B2', 'GATE_B3',
  'GATE_C1', 'GATE_C2', 'GATE_C3',
  'GATE_D1', 'GATE_D2',
  'GATE_A1', 'GATE_A2', 'GATE_A3',
]

const STORE_DESTINATIONS = [
  { id: 'STARBUCKS_T4', label: '☕  Starbucks — Terminal 4', icon: '☕' },
  { id: 'MC_DONALDS_T4', label: '🍔  McDonald\'s — Terminal 4', icon: '🍔' },
  { id: 'STARBUCKS_T5', label: '☕  Starbucks — Terminal 5', icon: '☕' },
  { id: 'DUNKIN_T5', label: '🍩  Dunkin\' — Terminal 5', icon: '🍩' },
  { id: 'SHAKE_SHACK_T7', label: '🍔  Shake Shack — Terminal 7', icon: '🍔' },
  { id: 'STARBUCKS_T8', label: '☕  Starbucks — Terminal 8', icon: '☕' },
  { id: 'RESTROOM_T4', label: '🚻  Restroom — Terminal 4', icon: '🚻' },
  { id: 'RESTROOM_T5', label: '🚻  Restroom — Terminal 5', icon: '🚻' },
  { id: 'RESTROOM_T7', label: '🚻  Restroom — Terminal 7', icon: '🚻' },
  { id: 'RESTROOM_T8', label: '🚻  Restroom — Terminal 8', icon: '🚻' },
]

// Generate gate destinations
const GATE_DESTINATIONS = GATES.map(g => {
  const letter = g.split('_')[1]?.[0] || '';
  let terminalName = "Terminal 4";
  if (letter === 'C') terminalName = "Terminal 5";
  if (letter === 'D') terminalName = "Terminal 7";
  if (letter === 'A') terminalName = "Terminal 8";
  
  const formattedGate = g.replace('GATE_', 'Gate ');
  return { id: g, label: `✈️  ${formattedGate} — ${terminalName}`, icon: '✈️' }
})

const DESTINATIONS = [...STORE_DESTINATIONS, ...GATE_DESTINATIONS]


const DEST_TERMINAL = {
  STARBUCKS_T4: 4, MC_DONALDS_T4: 4, RESTROOM_T4: 4,
  STARBUCKS_T5: 5, DUNKIN_T5: 5, RESTROOM_T5: 5,
  SHAKE_SHACK_T7: 7, RESTROOM_T7: 7,
  STARBUCKS_T8: 8, RESTROOM_T8: 8,
}

// Pre-compute gate options for the CustomSelect
const GATE_OPTIONS = GATES.map(g => {
  const letter = g.split('_')[1]?.[0] || '';
  let terminalName = "Terminal 4";
  if (letter === 'C') terminalName = "Terminal 5";
  if (letter === 'D') terminalName = "Terminal 7";
  if (letter === 'A') terminalName = "Terminal 8";
  
  const formattedGate = g.replace('GATE_', 'Gate ');
  return { id: g, label: `${terminalName} — ${formattedGate}` }
})

export default function TripForm({ onSubmit, loading, syncData, onLiveUpdate }) {
  const [airline, setAirline] = useState(null)           // { code, name, terminal } or null
  const [airlines, setAirlines] = useState([])            // fetched airline list
  const [experience, setExperience] = useState('normal')
  const [gate, setGate] = useState('GATE_B1')
  const [stops, setStops] = useState([{ destination: 'STARBUCKS_T4', stayMinutes: 15 }])
  const [walkingSpeed, setWalkingSpeed] = useState(1.4)
  const [itineraryMinutes, setItineraryMinutes] = useState(120)

  // Fetch airline list from /api/airlines on mount
  useEffect(() => {
    fetch('/api/airlines')
      .then(r => r.ok ? r.json() : [])
      .then(data => setAirlines(data))
      .catch(() => {})
  }, [])

  // When airline changes, auto-filter gates to the matched terminal
  const _GATE_TERMINAL = { B: 4, C: 5, D: 7, A: 8 }
  const availableGates = airline
    ? GATE_OPTIONS.filter(g => {
        const letter = g.id.split('_')[1]?.[0] || ''
        return _GATE_TERMINAL[letter] === airline.terminal
      })
    : GATE_OPTIONS

  // Auto-select first available gate when airline changes
  useEffect(() => {
    if (airline && availableGates.length > 0) {
      setGate(availableGates[0].id)
    }
  }, [airline?.code])  // eslint-disable-line react-hooks/exhaustive-deps

  // Broadcast live form state to parent for Chatbot context
  useEffect(() => {
    if (onLiveUpdate) {
      onLiveUpdate({
        gate,
        walking_speed: walkingSpeed,
        itinerary_minutes: itineraryMinutes,
        airline: airline?.code || null,
        experience,
      })
    }
  }, [gate, walkingSpeed, itineraryMinutes, airline, experience, onLiveUpdate])

  const updateStop = (index, field, value) => {
    setStops(prev => prev.map((s, i) => i === index ? { ...s, [field]: value } : s))
  }
  const addStop = () => {
    if (stops.length < 5) setStops(prev => [...prev, { destination: 'STARBUCKS_T4', stayMinutes: 15 }])
  }
  const removeStop = (index) => {
    if (stops.length > 1) setStops(prev => prev.filter((_, i) => i !== index))
  }

  // Sync form state when external data (e.g. from chat) changes
  useEffect(() => {
    if (syncData) {
      if (syncData.gate) setGate(syncData.gate)
      if (syncData.stops && syncData.stops.length > 0) {
        // Multi-stop: populate each stop row from the stops array
        setStops(syncData.stops.map(s => ({
          destination: s.destination,
          stayMinutes: s.stay_minutes || 15,
        })))
      } else if (syncData.destination) {
        // Single-stop: populate one row
        setStops([{ destination: syncData.destination, stayMinutes: syncData.stay_minutes || 15 }])
      }
      if (syncData.walking_speed) setWalkingSpeed(syncData.walking_speed)
      if (syncData.itinerary_minutes) setItineraryMinutes(syncData.itinerary_minutes)
      if (syncData.experience) setExperience(syncData.experience)
      // Sync airline selection back from chat-derived trips
      if (syncData.airline && airlines.length > 0) {
        const found = airlines.find(a => a.code === syncData.airline)
        if (found) setAirline(found)
      }
    }
  }, [syncData])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e) => {
    e.preventDefault()

    const letter = gate.split('_')[1]?.[0] || '';
    let departureTerminal = 4;
    if (letter === 'C') departureTerminal = 5;
    if (letter === 'D') departureTerminal = 7;
    if (letter === 'A') departureTerminal = 8;

    if (stops.length === 1) {
      // Single stop — use the existing /api/plan endpoint
      onSubmit({
        gate,
        destination: stops[0].destination,
        terminal: departureTerminal,
        stay_minutes: stops[0].stayMinutes,
        walking_speed: walkingSpeed,
        itinerary_minutes: itineraryMinutes,
        airline: airline?.code || undefined,
        experience,
      })
    } else {
      // Multi-stop — use /api/plan-multi endpoint
      onSubmit({
        _multi: true,
        gate,
        terminal: departureTerminal,
        stops: stops.map(s => ({ destination: s.destination, stay_minutes: s.stayMinutes })),
        walking_speed: walkingSpeed,
        itinerary_minutes: itineraryMinutes,
        airline: airline?.code || undefined,
        experience,
      })
    }
  }

  const speedLabel = walkingSpeed < 1.0 ? 'Slow' : walkingSpeed > 1.6 ? 'Fast' : 'Normal'

  return (
    <div className="glass-card trip-form-area">
      <div className="section-title">Plan Your Trip</div>
      <form onSubmit={handleSubmit} id="trip-form">

        {/* ── Airline Selector ──────────────────────── */}
        {airlines.length > 0 && (
          <div className="form-group">
            <label htmlFor="airline-select">Your Airline</label>
            <CustomSelect
              value={airline?.code || ''}
              onChange={(code) => {
                const found = airlines.find(a => a.code === code)
                setAirline(found || null)
              }}
              options={[
                { id: '', label: '✈️  Any airline' },
                ...airlines.map(a => ({ id: a.code, label: `✈️  ${a.name} (${a.code}) — Terminal ${a.terminal}` }))
              ]}
            />
          </div>
        )}

        {/* ── Experience Selector ──────────────────────── */}
        <div className="form-group">
          <label htmlFor="experience-select">Layover Experience</label>
          <CustomSelect
            value={experience}
            onChange={setExperience}
            options={[
              { id: 'beginner', label: 'Beginner (New to layovers)' },
              { id: 'normal', label: 'Normal (Average)' },
              { id: 'experienced', label: 'Experienced (Frequent flyer)' }
            ]}
          />
        </div>

        <div className="form-group">
          <label htmlFor="gate-select">Departure Gate</label>
          <CustomSelect
            value={gate}
            onChange={setGate}
            options={availableGates} 
          />
        </div>

        {/* ── Dynamic Stops ──────────────────────── */}
        {stops.map((stop, index) => (
          <div key={index} className="stop-card">
            <div className="stop-card-header">
              <span className="stop-card-label">Stop {index + 1}</span>
              {stops.length > 1 && (
                <button
                  type="button"
                  className="stop-remove-btn"
                  onClick={() => removeStop(index)}
                  title="Remove stop"
                >
                  🗑
                </button>
              )}
            </div>

            <div className="form-group">
              <label>Destination</label>
              <CustomSelect
                value={stop.destination}
                onChange={(val) => updateStop(index, 'destination', val)}
                options={DESTINATIONS}
              />
            </div>

            <div className="form-group">
              <label>
                Stay Duration
                <span className="range-value">{stop.stayMinutes} min</span>
              </label>
              <div className="range-wrapper">
                <input
                  type="range" min="5" max="60" step="5"
                  value={stop.stayMinutes}
                  onChange={e => updateStop(index, 'stayMinutes', Number(e.target.value))}
                  style={{ background: `linear-gradient(to right, var(--cyan) 0%, var(--blue) ${((stop.stayMinutes - 5) / 55) * 100}%, var(--bg-surface) ${((stop.stayMinutes - 5) / 55) * 100}%)` }}
                />
              </div>
            </div>
          </div>
        ))}

        {stops.length < 5 && (
          <button type="button" className="btn-add-stop" onClick={addStop}>
            ➕ Add Stop
          </button>
        )}

        <div className="form-group">
          <label htmlFor="speed-slider">
            Walking Speed
            <span className="range-value">{walkingSpeed} m/s · {speedLabel}</span>
          </label>
          <div className="range-wrapper">
            <input
              id="speed-slider" type="range"
              min="0.5" max="2.0" step="0.1"
              value={walkingSpeed}
              onChange={e => setWalkingSpeed(Number(e.target.value))}
              style={{
                background: `linear-gradient(to right, var(--cyan) 0%, var(--blue) ${((walkingSpeed - 0.5) / 1.5) * 100}%, var(--bg-surface) ${((walkingSpeed - 0.5) / 1.5) * 100}%)`
              }}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="layover-slider">
            Layover Duration
            <span className="range-value">{itineraryMinutes} min · {(itineraryMinutes / 60).toFixed(1)}h</span>
          </label>
          <div className="range-wrapper">
            <input
              id="layover-slider" type="range"
              min="30" max="360" step="10"
              value={itineraryMinutes}
              onChange={e => setItineraryMinutes(Number(e.target.value))}
              style={{
                background: `linear-gradient(to right, var(--cyan) 0%, var(--violet) ${((itineraryMinutes - 30) / 330) * 100}%, var(--bg-surface) ${((itineraryMinutes - 30) / 330) * 100}%)`
              }}
            />
          </div>
        </div>

        <button type="submit" id="submit-btn" className="btn-primary" disabled={loading}>
          {loading ? (
            <><span className="loading-spinner" /> Analyzing Flight Data...</>
          ) : (
            '✈️  Check Feasibility'
          )}
        </button>
      </form>
    </div>
  )
}
