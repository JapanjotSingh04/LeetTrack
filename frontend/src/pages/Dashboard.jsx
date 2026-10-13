import { useCallback, useEffect, useState } from 'react'
import Navbar from '../components/Navbar'
import CapacityBar from '../components/CapacityBar'
import RevisionCard from '../components/RevisionCard'
import QuestionCard from '../components/QuestionCard'
import { SkeletonCard } from '../components/LoadingSpinner'
import { useToast } from '../components/Toast'
import * as api from '../api/api'

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function Dashboard() {
  const [user, setUser] = useState(null)
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [simulatedDate, setSimulatedDate] = useState(todayStr())
  const showToast = useToast()

  const isToday = simulatedDate === todayStr()

  const load = useCallback(async () => {
    setError(null)
    try {
      const [userData, planData] = await Promise.all([
        api.getUser(),
        api.getDailyPlan(simulatedDate),
      ])
      setUser(userData)
      setPlan(planData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [simulatedDate])

  // Re-fetch the dashboard (capacity, due revisions, new-question mix)
  // whenever the simulated date changes.
  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  async function handleSolveQuestion(question) {
    try {
      const result = await api.completeQuestion({
        question_id: question.question_id,
        platform: question.platform,
        difficulty: question.difficulty,
      })
      showToast(
        `✓ "${question.title}" marked as solved! Next revision: ${result.due_date || 'n/a'}`
      )
      await load()
    } catch (err) {
      showToast(err.message, 'error')
    }
  }

  async function handleCompleteRevision(revision) {
    try {
      const result = await api.completeRevision({
        question_id: revision.question_id,
        platform: revision.platform,
        difficulty: revision.difficulty,
        revision_counter: revision.revision_counter,
      })
      showToast(
        result.completed
          ? `✓ "${revision.title}" — all revisions complete!`
          : `✓ Revision complete! Next revision: ${result.due_date}`
      )
      await load()
    } catch (err) {
      showToast(err.message, 'error')
    }
  }

  return (
    <>
      <Navbar title="LeetTrack" subtitle="Dashboard" />
      <div className="px-8 py-6 max-w-5xl">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-ink">
              {isToday ? greeting() : 'Viewing plan for'}{isToday && user ? `, ${user.username}` : ''} 👋
            </h2>
            <p className="text-ink-muted mt-1">
              {isToday
                ? "Here's your DSA plan for today."
                : `Simulated plan for ${simulatedDate} — no data is being changed.`}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <label className="text-xs text-ink-muted" htmlFor="simulated-date">
              Simulated date
            </label>
            <input
              id="simulated-date"
              type="date"
              value={simulatedDate}
              onChange={(e) => setSimulatedDate(e.target.value)}
              className="px-3 py-2 rounded-lg bg-base-card border border-base-border text-sm text-ink focus:outline-none focus:border-accent [color-scheme:dark]"
            />
            {!isToday && (
              <button
                onClick={() => setSimulatedDate(todayStr())}
                className="text-sm px-3 py-2 rounded-lg border border-base-border text-ink-muted hover:border-accent hover:text-accent transition-colors whitespace-nowrap"
              >
                Reset to today
              </button>
            )}
          </div>
        </div>

        {!isToday && !error && (
          <div className="rounded-card border border-accent/30 bg-accent-muted/40 px-4 py-2.5 mb-6 text-sm text-accent">
            You're viewing a simulated date. Completing a question or revision still records against today's real date.
          </div>
        )}

        {error && <ErrorBanner message={error} onRetry={load} />}

        {loading && !error && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        )}

        {plan && !error && (
          <>
            <div className="mb-8">
              <CapacityBar
                dailyCapacity={plan.daily_capacity}
                revisionCapacity={plan.revision_capacity}
                newCapacity={plan.new_capacity}
                remainingCapacity={plan.remaining_capacity}
              />
            </div>

            <Section title={isToday ? "Today's revision" : 'Revision queue'} count={plan.revisions.length}>
              {plan.revisions.length === 0 ? (
                <EmptyState
                  emoji="🎉"
                  message={isToday ? 'No revisions due today!' : `No revisions due by ${simulatedDate}.`}
                />
              ) : (
                <CardGrid>
                  {plan.revisions.map((r) => (
                    <RevisionCard
                      key={`${r.question_id}-${r.platform}`}
                      revision={r}
                      onComplete={handleCompleteRevision}
                    />
                  ))}
                </CardGrid>
              )}
            </Section>

            <Section title={isToday ? "Today's new questions" : 'New questions'} count={plan.new_questions.length}>
              {plan.new_questions.length === 0 ? (
                <EmptyState message="You've completed all currently available questions." />
              ) : (
                <CardGrid>
                  {plan.new_questions.map((q) => (
                    <QuestionCard
                      key={`${q.question_id}-${q.platform}`}
                      question={q}
                      onComplete={handleSolveQuestion}
                    />
                  ))}
                </CardGrid>
              )}
            </Section>
          </>
        )}
      </div>
    </>
  )
}

function Section({ title, count, children }) {
  return (
    <section className="mb-8">
      <div className="flex items-baseline gap-2 mb-3">
        <h3 className="text-sm font-medium text-ink">{title}</h3>
        {typeof count === 'number' && <span className="text-xs text-ink-faint">{count}</span>}
      </div>
      {children}
    </section>
  )
}

function CardGrid({ children }) {
  return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
}

function EmptyState({ emoji, message }) {
  return (
    <div className="rounded-card border border-dashed border-base-border p-8 text-center text-ink-muted">
      {emoji && <div className="text-2xl mb-2">{emoji}</div>}
      <p className="text-sm">{message}</p>
    </div>
  )
}

function ErrorBanner({ message, onRetry }) {
  return (
    <div className="rounded-card border border-hard/30 bg-hard-bg p-4 mb-6">
      <p className="text-sm text-hard font-medium">Unable to load today's plan.</p>
      <p className="text-sm text-ink-muted mt-1">
        Make sure the backend server and MySQL are running. ({message})
      </p>
      <button
        onClick={onRetry}
        className="mt-3 text-sm px-3 py-1.5 rounded-lg border border-base-border text-ink hover:border-accent hover:text-accent transition-colors"
      >
        Retry
      </button>
    </div>
  )
}
