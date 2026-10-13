export default function CapacityBar({
  dailyCapacity = 100,
  revisionCapacity = 0,
  newCapacity = 0,
  remainingCapacity = 0,
}) {
  const used = revisionCapacity + newCapacity
  const overCapacity = used > dailyCapacity
  const scale = Math.max(dailyCapacity, used, 1)
  const revisionPct = Math.min(100, (revisionCapacity / scale) * 100)
  const newPct = Math.min(100 - revisionPct, (newCapacity / scale) * 100)

  return (
    <div className="rounded-card border border-base-border bg-base-card p-5 shadow-card">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="text-sm font-medium text-ink-muted">Today's capacity</h2>
        <p className={`font-mono text-2xl font-semibold ${overCapacity ? 'text-hard' : 'text-ink'}`}>
          {used}
          <span className="text-ink-faint text-base font-normal"> / {dailyCapacity}</span>
        </p>
      </div>

      {overCapacity && (
        <p role="status" className="text-xs text-hard mb-3">
          Your due-revision backlog exceeds today's capacity by {used - dailyCapacity} units. The full due queue is shown; consider prioritizing overdue revisions.
        </p>
      )}
      <div className={`h-2.5 w-full rounded-full ${overCapacity ? 'bg-hard/20' : 'bg-base-border'} overflow-hidden flex`}>
        <div
          className="h-full bg-accent transition-all duration-500"
          style={{ width: `${revisionPct}%` }}
          title={`Revisions: ${revisionCapacity}`}
        />
        <div
          className="h-full bg-easy transition-all duration-500"
          style={{ width: `${newPct}%` }}
          title={`New questions: ${newCapacity}`}
        />
      </div>

      <div className="grid grid-cols-3 gap-4 mt-5">
        <Stat label="Revision capacity" value={revisionCapacity} dotClass="bg-accent" />
        <Stat label="New question capacity" value={newCapacity} dotClass="bg-easy" />
        <Stat label="Remaining capacity" value={remainingCapacity} dotClass="bg-base-border" />
      </div>
    </div>
  )
}

function Stat({ label, value, dotClass }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-ink-muted mb-1">
        <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
        {label}
      </div>
      <p className="font-mono text-lg font-semibold text-ink">{value}</p>
    </div>
  )
}
