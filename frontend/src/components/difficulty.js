export const DIFFICULTY_STYLES = {
  Easy: { text: 'text-easy', bg: 'bg-easy-bg', border: 'border-easy/30' },
  Medium: { text: 'text-medium', bg: 'bg-medium-bg', border: 'border-medium/30' },
  Hard: { text: 'text-hard', bg: 'bg-hard-bg', border: 'border-hard/30' },
}

export function difficultyStyle(difficulty) {
  return DIFFICULTY_STYLES[difficulty] || DIFFICULTY_STYLES.Easy
}
