export default function DecisionBanner({ decision, action, loading }) {
  if (!decision) {
    return (
      <div className="glass-card decision-area decision-empty">
        {loading ? (
          <div className="decision-loading-state">
            <span className="loading-spinner decision-spinner" />
            <div className="decision-scanning-text">Analysing Flight Data…</div>
            <div className="decision-scanning-sub">Running AI risk assessment</div>
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">✈️</div>
            <p>Configure your trip and hit <strong>Check Feasibility</strong> to get an AI-powered decision</p>
          </div>
        )}
      </div>
    )
  }

  const cls = decision === 'GO' ? 'go' : decision === 'MAYBE' ? 'maybe' : 'no'
  const emoji = decision === 'GO' ? '✅' : decision === 'MAYBE' ? '⚠️' : '🚫'

  return (
    <div className={`decision-banner decision-area ${cls}${loading ? ' decision-refreshing' : ''}`} id="decision-banner">
      {/* Overlay when re-submitting over existing data */}
      {loading && (
        <div className="decision-refresh-overlay">
          <span className="loading-spinner" />
          <span className="decision-refresh-text">Re-evaluating…</span>
        </div>
      )}
      <div className="decision-text">{emoji} {decision}</div>
      <div className="decision-subtitle">{action}</div>
    </div>
  )
}
