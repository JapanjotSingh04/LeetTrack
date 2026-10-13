import { useCallback, useEffect, useMemo, useState } from 'react'
import Navbar from '../components/Navbar'
import { SkeletonCard } from '../components/LoadingSpinner'
import { difficultyStyle } from '../components/difficulty'
import { useToast } from '../components/Toast'
import * as api from '../api/api'

const DIFFICULTIES = ['All', 'Easy', 'Medium', 'Hard']

export default function Questions() {
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [difficulty, setDifficulty] = useState('All')
  const showToast = useToast()

  const load = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      const filters = difficulty !== 'All' ? { difficulty } : {}
      const data = await api.getQuestions(filters)
      setQuestions(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [difficulty])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(() => {
    if (!search.trim()) return questions
    const q = search.toLowerCase()
    return questions.filter((item) => item.title.toLowerCase().includes(q))
  }, [questions, search])

  async function handleSolve(question) {
    try {
      const result = await api.completeQuestion({
        question_id: question.question_id,
        platform: question.platform,
        difficulty: question.difficulty,
      })
      showToast(`✓ "${question.title}" marked as solved! Next revision: ${result.due_date || 'n/a'}`)
      await load()
    } catch (err) {
      showToast(err.message, 'error')
    }
  }

  return (
    <>
      <Navbar title="Questions" subtitle="Browse and search the full question bank" />
      <div className="px-8 py-6 max-w-5xl">
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by title…"
            className="flex-1 px-3.5 py-2.5 rounded-lg bg-base-card border border-base-border text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent"
          />
          <div className="flex gap-1.5">
            {DIFFICULTIES.map((d) => (
              <button
                key={d}
                onClick={() => setDifficulty(d)}
                className={`px-3 py-2 rounded-lg text-sm border transition-colors ${
                  difficulty === d
                    ? 'bg-accent-muted border-accent/50 text-accent'
                    : 'border-base-border text-ink-muted hover:text-ink'
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="rounded-card border border-hard/30 bg-hard-bg p-4 mb-6 text-sm text-hard">
            Unable to load questions. ({error})
          </div>
        )}

        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="rounded-card border border-dashed border-base-border p-8 text-center text-ink-muted">
            <p className="text-sm">No questions match your search.</p>
          </div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((q) => (
              <QuestionRow key={`${q.question_id}-${q.platform}`} question={q} onSolve={handleSolve} />
            ))}
          </div>
        )}
      </div>
    </>
  )
}

function QuestionRow({ question, onSolve }) {
  const style = difficultyStyle(question.difficulty)
  const solved = question.solved === 1

  return (
    <div className="rounded-card border border-base-border bg-base-card p-4 shadow-card flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-ink font-medium leading-snug text-sm">{question.title}</h3>
        {solved && <span className="text-xs text-easy shrink-0">Solved</span>}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs px-2 py-0.5 rounded border ${style.bg} ${style.text} ${style.border}`}>
          {question.difficulty}
        </span>
        {question.topic && <span className="text-xs text-ink-muted">{question.topic}</span>}
        <span className="text-xs text-ink-faint capitalize">{question.platform}</span>
      </div>

      <div className="flex gap-2 mt-1">
        <a
          href={question.url}
          target="_blank"
          rel="noreferrer"
          className="flex-1 text-center text-sm px-3 py-2 rounded-lg border border-base-border text-ink hover:border-accent hover:text-accent transition-colors"
        >
          Open
        </a>
        {!solved && (
          <button
            onClick={() => onSolve(question)}
            className="flex-1 text-sm px-3 py-2 rounded-lg bg-accent text-white hover:bg-accent-hover transition-colors"
          >
            Mark solved
          </button>
        )}
      </div>
    </div>
  )
}
