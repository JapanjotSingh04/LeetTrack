export default function LoadingSpinner({ label = 'Loading…', size = 'md' }) {
  const dims = size === 'sm' ? 'w-4 h-4 border-2' : 'w-8 h-8 border-[3px]'
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-ink-muted">
      <div
        className={`${dims} rounded-full border-base-border border-t-accent animate-spin`}
        role="status"
        aria-label={label}
      />
      {label && <p className="text-sm">{label}</p>}
    </div>
  )
}

export function SkeletonCard() {
  return (
    <div className="rounded-card border border-base-border bg-base-card p-4 animate-pulse">
      <div className="h-3 w-24 bg-base-border rounded mb-3" />
      <div className="h-4 w-3/4 bg-base-border rounded mb-2" />
      <div className="h-3 w-1/2 bg-base-border rounded mb-4" />
      <div className="flex gap-2">
        <div className="h-8 w-24 bg-base-border rounded" />
        <div className="h-8 w-28 bg-base-border rounded" />
      </div>
    </div>
  )
}
