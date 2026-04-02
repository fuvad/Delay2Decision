export default function RiskPanel({ data, loading }) {
  if (!data) {
    // No prior result — show the empty placeholder (or a full loading skeleton)
    return (
      <div className="glass-card risk-area">
        <div className="section-title">Risk Analysis</div>
        {loading ? (
          <div className="risk-loading-skeleton">
            <span className="loading-spinner" />
            <p className="risk-loading-text">Analysing flight data…</p>
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">📊</div>
            <p>Risk metrics will appear after plan analysis</p>
          </div>
        )}
      </div>
    )
  }

  const riskCls = data.risk_level === 'low' ? 'risk-low'
    : data.risk_level === 'medium' ? 'risk-medium' : 'risk-high'

  // Gauge calculation: usable_time as percentage of itinerary_minutes
  const usable = data.usable_time || 0
  const itinerary = data.itinerary_minutes || 120
  const required = data.planner?.required_minutes ?? data.total_required ?? 0
  const gaugePercent = itinerary > 0 ? Math.min(100, (usable / itinerary) * 100) : 0
  const circumference = 2 * Math.PI * 54 // r=54
  const dashOffset = circumference - (gaugePercent / 100) * circumference

  const gaugeColor = data.risk_level === 'low' ? 'var(--go)'
    : data.risk_level === 'medium' ? 'var(--maybe)' : 'var(--no)'

  const violated = data.constraints?.violated || []
  const constraints = [
    { name: 'Gate Reachability', key: 'gate_reachability' },
    { name: 'Security Clearance', key: 'security_clearance' },
    { name: 'Buffer Safety', key: 'buffer_respected' },
  ]

  return (
    <div className={`glass-card risk-area${loading ? ' risk-loading' : ''}`} id="risk-panel">
      <div className="section-title">Risk Analysis</div>

      {/* Loading overlay — shown on top of stale data while re-calculating */}
      {loading && (
        <div className="risk-refresh-overlay">
          <span className="loading-spinner" />
          <span className="risk-loading-text">Recalculating Risk…</span>
        </div>
      )}
      <div style={{ display: 'flex', gap: '1.25rem', alignItems: 'flex-start' }}>
        {/* Circular Gauge */}
        <div className="gauge-container">
          <div className="gauge-ring">
            <svg viewBox="0 0 120 120">
              <circle className="gauge-bg" cx="60" cy="60" r="54" />
              <circle
                className="gauge-fill"
                cx="60" cy="60" r="54"
                stroke={gaugeColor}
                strokeDashoffset={dashOffset}
              />
            </svg>
            <div className="gauge-label">
              <div className="gauge-value" style={{ color: gaugeColor }}>
                {gaugePercent.toFixed(0)}%
              </div>
              <div className="gauge-subtitle">Usable</div>
            </div>
          </div>
        </div>

        {/* Metrics + Constraints */}
        <div style={{ flex: 1 }}>
          <div className="risk-panel">
            <div className="risk-metric">
              <div className={`metric-value ${riskCls}`}>
                {data.risk_level?.toUpperCase()}
              </div>
              <div className="metric-label">Delay Risk</div>
            </div>
            <div className="risk-metric">
              <div className="metric-value" style={{ color: 'var(--cyan)' }}>
                {usable.toFixed(0)}
              </div>
              <div className="metric-label">Usable min</div>
            </div>
            <div className="risk-metric">
              <div className="metric-value" style={{ color: 'var(--purple)' }}>
                {required < 0 ? <span style={{ display: 'inline-block', transform: 'scale(1.6)' }}>∞</span> : required.toFixed(0)}
              </div>
              <div className="metric-label">Required</div>
            </div>
          </div>

          <div style={{ marginTop: '0.75rem' }}>
            <ul className="constraints-list">
              {[
                { name: 'Gate Reachability', key: 'Gate Reachability' },
                { name: 'Security Clearance', key: 'Security Clearance' },
                { name: 'Delay Resilience',   key: 'Delay Resilience'   },
              ].map(c => {
                const passed = !violated.includes(c.key)
                return (
                  <li key={c.key}>
                    <span className={passed ? 'check-icon' : 'cross-icon'}>
                      {passed ? '✓' : '✗'}
                    </span>
                    {c.name}
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      </div>

      {/* AI Explanation */}
      {data.explanation && (
        <div className="explanation-box">
          {data.explanation}
        </div>
      )}
    </div>
  )
}
