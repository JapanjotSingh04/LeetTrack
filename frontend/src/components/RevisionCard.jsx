import { useState } from 'react'
import { difficultyStyle } from './difficulty'

export default function RevisionCard({ revision, onComplete }) {
  const [submitting, setSubmitting] = useState(false)
  const style = difficultyStyle(revision.difficulty)
  const isDue = revision.due_date && revision.due_date <= new Date().toISOString().slice(0, 10)

  async function handleComplete() {
    if (submitting) return
    setSubmitting(true)
    try {
      await onComplete(revision)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-card border border-base-border bg-base-card p-4 shadow-card flex flex-col gap-3 border-l-2 border-l-accent">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted">
          <span className="w-1.5 h-1.5 rounded-full bg-medium" />
          Revision
        </span>
        <span className={`text-xs ${isDue ? 'text-hard' : 'text-ink-muted'}`}>
          Due {revision.due_date === new Date().toISOString().slice(0, 10) ? 'today' : revision.due_date}
        </span>
      </div>

      <div>
        <h3 className="text-ink font-medium leading-snug">{revision.title}</h3>
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded border ${style.bg} ${style.text} ${style.border}`}>
            {revision.difficulty}
          </span>
          {revision.topic && <span className="text-xs text-ink-muted">{revision.topic}</span>}
          <span className="font-mono text-xs text-ink-faint">Revision #{revision.revision_counter + 1}</span>
        </div>
      </div>

      <div className="flex gap-2 mt-1">
        <a
          href={revision.url}
          target="_blank"
          rel="noreferrer"
          className="flex-1 text-center text-sm px-3 py-2 rounded-lg border border-base-border text-ink hover:border-accent hover:text-accent transition-colors"
        >
          Open problem
        </a>
        {onComplete && (
          <button
            onClick={handleComplete}
            disabled={submitting}
            className="flex-1 text-sm px-3 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Saving…' : 'Complete revision'}
          </button>
        )}
      </div>
    </div>
  )
}
