export default function DifficultyBadge({ level }) {
  const colors = {
    beginner: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    intermediate: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    advanced: 'bg-rose-500/20 text-rose-300 border-rose-500/30'
  };

  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium border ${colors[level] || colors.intermediate}`}>
      {level}
    </span>
  );
}
