import CustomSelect from './CustomSelect'

const GATES = [
  'GATE_B1', 'GATE_B2', 'GATE_B3',
  'GATE_C1', 'GATE_C2', 'GATE_C3',
  'GATE_D1', 'GATE_D2',
  'GATE_A1', 'GATE_A2', 'GATE_A3',
]

const GATE_OPTIONS = GATES.map(g => ({
  id: g,
  label: g.replace(/_/g, ' ')
}))

export default function GateOverride({ currentGate, onOverride }) {
  const filteredOptions = GATE_OPTIONS.filter(opt => opt.id.charAt(5) === currentGate.charAt(5))

  return (
    <div className="gate-override-wrapper">
      <div className="gate-override">
        <span className="override-icon">🔄</span>
        <span className="override-label">Gate Changed?</span>
        <div style={{ width: '160px' }}>
          <CustomSelect
            value={currentGate}
            onChange={onOverride}
            options={filteredOptions}
          />
        </div>
      </div>
    </div>
  )
}
