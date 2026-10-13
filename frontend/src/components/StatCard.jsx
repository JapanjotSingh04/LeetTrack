export default function StatCard({ label, value, accentClass = 'text-ink' }) {
  return (
    <div className="rounded-card border border-base-border bg-base-card p-4 shadow-card">
      <p className="text-xs text-ink-muted mb-1.5">{label}</p>
      <p className={`font-mono text-2xl font-semibold ${accentClass}`}>{value}</p>
    </div>
  )
}
