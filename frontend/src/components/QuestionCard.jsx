import { useState } from 'react'
import { difficultyStyle } from './difficulty'

export default function QuestionCard({ question, onComplete, showSolvedBadge = false }) {
  const [submitting, setSubmitting] = useState(false)
  const style = difficultyStyle(question.difficulty)

  async function handleComplete() {
    if (submitting) return
    setSubmitting(true)
    try {
      await onComplete(question)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-card border border-base-border bg-base-card p-4 shadow-card flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-xs font-medium text-accent">
          <span className="w-1.5 h-1.5 rounded-full bg-accent" />
          New question
        </span>
        {question.solved === 1 && showSolvedBadge && (
          <span className="text-xs text-easy">Solved</span>
        )}
      </div>

      <div>
        <h3 className="text-ink font-medium leading-snug">{question.title}</h3>
        <div className="flex items-center gap-2 mt-1.5 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded border ${style.bg} ${style.text} ${style.border}`}>
            {question.difficulty}
          </span>
          {question.topic && <span className="text-xs text-ink-muted">{question.topic}</span>}
          {question.platform && (
            <span className="text-xs text-ink-faint capitalize">{question.platform}</span>
          )}
        </div>
      </div>

      <div className="flex gap-2 mt-1">
        <a
          href={question.url}
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
            {submitting ? 'Saving…' : 'Mark as solved'}
          </button>
        )}
      </div>
    </div>
  )
}
