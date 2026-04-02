function getDestIcon(nodeId) {
  if (!nodeId) return '🍽️'
  if (nodeId.includes('RESTROOM')) return '🚻'
  if (nodeId.includes('STARBUCKS')) return '☕'
  if (nodeId.includes('DUNKIN')) return '🍩'
  if (nodeId.includes('SHAKE_SHACK') || nodeId.includes('MC_DONALDS')) return '🍔'
  if (nodeId.includes('GATE')) return '✈️'
  return '🏁'
}

const Arrow = () => (
  <div className="timeline-arrow" style={{ flexShrink: 0, minWidth: '24px', justifyContent: 'center' }}>
    <svg width="20" height="12" viewBox="0 0 20 12" fill="none">
      <path d="M0 6H18M18 6L13 1M18 6L13 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  </div>
)

export default function Timeline({ simulation, itineraryMinutes, bufferMinutes, usableTime, destination, legs, totalRequired, loading }) {
  // ── Multi-stop mode ──────────────────────────────────────────────
  if (legs && legs.length > 0) {
    const usable = usableTime ?? Math.max(0, (itineraryMinutes || 120) - (bufferMinutes || 0))
    const total = totalRequired ?? legs.reduce((s, l) => s + l.walk_minutes + l.stay_minutes, 0)
    const spare = Math.max(0, usable - total)

    return (
      <div className={`glass-card timeline-area${loading ? ' timeline-loading' : ''}`} id="timeline">
        <div className="section-title">Trip Timeline</div>
        {loading && (
          <div className="timeline-refresh-overlay">
            <span className="loading-spinner" />
            <span className="risk-loading-text">Recalculating Timeline…</span>
          </div>
        )}
        <div className="timeline">
          {legs.map((leg, i) => (
            <div key={i} style={{ display: 'contents' }}>
              {i > 0 && <Arrow />}
              {/* Walk segment */}
              <div className="timeline-segment walk" style={{ flex: Math.max(leg.walk_minutes, 2) }}>
                <div className="seg-icon">🚶</div>
                <div className="seg-time">{leg.walk_minutes.toFixed(1)}</div>
                <div className="seg-label">{i === legs.length - 1 ? 'Walk Back' : i === 0 ? 'Walk There' : 'Walk'}</div>
              </div>
              {/* Stay segment — only for non-return legs */}
              {leg.stay_minutes > 0 && (
                <>
                  <Arrow />
                  <div className="timeline-segment stay" style={{ flex: Math.max(leg.stay_minutes, 5) }}>
                    <div className="seg-icon">{getDestIcon(leg.to_node)}</div>
                    <div className="seg-time">{leg.stay_minutes.toFixed(0)}</div>
                    <div className="seg-label">{leg.to_node.replace(/_T\d$/, '').replace(/_/g, ' ')}</div>
                  </div>
                </>
              )}
            </div>
          ))}
          {spare > 0 && (
            <>
              <Arrow />
              <div className="timeline-segment buffer" style={{ flex: Math.max(spare, 5) }}>
                <div className="seg-icon">⏳</div>
                <div className="seg-time">{spare.toFixed(0)}</div>
                <div className="seg-label">Time Left</div>
              </div>
            </>
          )}
        </div>
        <div className="timeline-summary">
          ✈️ Total trip: <strong>{total.toFixed(1)} min</strong> out of <strong>{usable.toFixed(0)} min</strong> usable
          {spare > 0 && <> · <span style={{ color: 'var(--go)' }}>{spare.toFixed(0)} min spare</span></>}
        </div>
      </div>
    )
  }

  // ── Single-stop mode (original) ──────────────────────────────────
  if (!simulation || simulation.error) {
    return (
      <div className="glass-card timeline-area">
        <div className="section-title">Trip Timeline</div>
        <div className="empty-state">
          <div className="empty-icon">🗺️</div>
          <p>{simulation?.error || 'Your trip timeline will be visualized here'}</p>
        </div>
      </div>
    )
  }

  const walkMin = simulation.walk_minutes || 0
  const stayMin = simulation.stay_minutes || 0
  const walkHalf = walkMin / 2
  const usable = usableTime != null ? usableTime : Math.max(0, (itineraryMinutes || 120) - (bufferMinutes || 0))
  const totalTrip = walkMin + stayMin
  const remaining = Math.max(0, usable - totalTrip)

  let destIcon = '🍽️'
  if (destination) {
    if (destination.includes('RESTROOM')) destIcon = '🚻'
    else if (destination.includes('STARBUCKS')) destIcon = '☕'
    else if (destination.includes('DUNKIN')) destIcon = '🍩'
    else if (destination.includes('SHAKE_SHACK') || destination.includes('MC_DONALDS')) destIcon = '🍔'
    else if (destination.includes('GATE')) destIcon = '✈️'
  }

  return (
    <div className={`glass-card timeline-area${loading ? ' timeline-loading' : ''}`} id="timeline">
      <div className="section-title">Trip Timeline</div>
      {loading && (
        <div className="timeline-refresh-overlay">
          <span className="loading-spinner" />
          <span className="risk-loading-text">Recalculating Timeline…</span>
        </div>
      )}

      <div className="timeline">
        <div className="timeline-segment walk" style={{ flex: Math.max(walkHalf, 3) }}>
          <div className="seg-icon">🚶</div>
          <div className="seg-time">{walkHalf.toFixed(1)}</div>
          <div className="seg-label">Walk There</div>
        </div>

        <Arrow />

        <div className="timeline-segment stay" style={{ flex: Math.max(stayMin, 5) }}>
          <div className="seg-icon">{destIcon}</div>
          <div className="seg-time">{stayMin.toFixed(0)}</div>
          <div className="seg-label">At Destination</div>
        </div>

        <Arrow />

        <div className="timeline-segment walk" style={{ flex: Math.max(walkHalf, 3) }}>
          <div className="seg-icon">🚶</div>
          <div className="seg-time">{walkHalf.toFixed(1)}</div>
          <div className="seg-label">Walk Back</div>
        </div>

        {remaining > 0 && (
          <>
            <Arrow />
            <div className="timeline-segment buffer" style={{ flex: Math.max(remaining, 5) }}>
              <div className="seg-icon">⏳</div>
              <div className="seg-time">{remaining.toFixed(0)}</div>
              <div className="seg-label">Time Left</div>
            </div>
          </>
        )}
      </div>

      <div className="timeline-summary">
        ✈️ Total trip: <strong>{totalTrip.toFixed(1)} min</strong> out of <strong>{usable.toFixed(0)} min</strong> usable
        {remaining > 0 && <> · <span style={{ color: 'var(--go)' }}>{remaining.toFixed(0)} min spare</span></>}
      </div>
    </div>
  )
}
