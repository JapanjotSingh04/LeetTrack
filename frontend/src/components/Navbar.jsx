export default function Navbar({ title, subtitle }) {
  return (
    <header className="border-b border-base-border bg-base/80 backdrop-blur px-8 py-5 sticky top-0 z-10">
      <h1 className="text-lg font-semibold text-ink">{title}</h1>
      {subtitle && <p className="text-sm text-ink-muted mt-0.5">{subtitle}</p>}
    </header>
  )
}
