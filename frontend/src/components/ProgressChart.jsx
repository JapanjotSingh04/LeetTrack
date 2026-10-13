import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const DIFFICULTY_COLORS = { Easy: '#3FB950', Medium: '#E3A008', Hard: '#F85149' }

const tooltipStyle = {
  background: '#141924',
  border: '1px solid #232A38',
  borderRadius: 8,
  fontSize: 12,
  color: '#E7EAF2',
}

export function DifficultyBarChart({ easy, medium, hard }) {
  const data = [
    { name: 'Easy', count: easy },
    { name: 'Medium', count: medium },
    { name: 'Hard', count: hard },
  ]

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} barSize={40}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1A2029" vertical={false} />
        <XAxis dataKey="name" stroke="#5B6478" fontSize={12} tickLine={false} axisLine={false} />
        <YAxis stroke="#5B6478" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: '#1A2029' }} />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={DIFFICULTY_COLORS[entry.name]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function SolvedOverTimeChart({ data }) {
  const formatted = data.map((d) => ({ date: d.solved_date, count: d.count }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={formatted}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1A2029" vertical={false} />
        <XAxis dataKey="date" stroke="#5B6478" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="#5B6478" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: '#232A38' }} />
        <Line type="monotone" dataKey="count" stroke="#5B8DEF" strokeWidth={2} dot={{ r: 3, fill: '#5B8DEF' }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
