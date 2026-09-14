import { useState } from 'react';
import { BookOpen, Check, X, Sparkles, ChevronDown, ChevronUp, TrendingUp, Users, GitBranch, Brain, AlertTriangle } from 'lucide-react';
import DifficultyBadge from './DifficultyBadge';

const FACTOR_CONFIG = {
  prerequisite: { icon: GitBranch, label: 'Prerequisites', colorClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' },
  interest: { icon: Sparkles, label: 'Interest Match', colorClass: 'bg-violet-500/20 text-violet-300 border-violet-500/30' },
  collaborative: { icon: Users, label: 'Peer Pattern', colorClass: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
  gpa: { icon: TrendingUp, label: 'Grade Prediction', colorClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' },
  gpa_warning: { icon: AlertTriangle, label: 'GPA Impact', colorClass: 'bg-rose-500/20 text-rose-300 border-rose-500/30' },
  query: { icon: Brain, label: 'Query Match', colorClass: 'bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/30' },
};

function FactorPill({ factor }) {
  const config = FACTOR_CONFIG[factor.type] || FACTOR_CONFIG.interest;
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs border ${config.colorClass}`}>
      <Icon className="w-3 h-3 flex-shrink-0" />
      <span className="truncate max-w-[200px]">{factor.description}</span>
      {factor.points !== 0 && (
        <span className="opacity-60">({factor.points > 0 ? '+' : ''}{factor.points})</span>
      )}
    </span>
  );
}

function PredictedGradeBadge({ prediction }) {
  if (!prediction) return null;

  const colorClass = prediction.predictedGPA >= 3.5
    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
    : prediction.predictedGPA >= 3.0
      ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
      : 'bg-rose-500/20 text-rose-300 border-rose-500/30';

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border ${colorClass}`} title={`Based on ${prediction.sampleSize} students, course avg: ${prediction.courseAvgGPA}`}>
      <TrendingUp className="w-3.5 h-3.5" />
      <span>Predicted: <strong>{prediction.predictedLetter}</strong></span>
      <span className="opacity-60">({prediction.difficultyIndicator})</span>
    </div>
  );
}

export default function CourseCard({ course }) {
  const [expanded, setExpanded] = useState(false);

  const courseName = course.name || course.course_name || 'Unnamed Course';
  const courseId = course.id || course.course_number || 'N/A';
  const courseCredits = course.credits ?? course.units ?? 0;
  const courseDifficulty = course.difficulty || course.level || 'intermediate';
  const factors = course.explanationFactors || [];
  const prediction = course.predictedGrade || null;

  const visibleFactors = expanded ? factors : factors.slice(0, 2);

  return (
    <div className="group relative bg-gradient-to-br from-slate-800/50 to-slate-900/50 border border-slate-700/50 rounded-xl p-5 hover:border-violet-500/50 transition-all duration-300 hover:shadow-xl hover:shadow-violet-500/10 hover:-translate-y-1">
      <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/5 rounded-full blur-3xl group-hover:bg-violet-500/10 transition-all duration-500" />

      <div className="relative">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-xl font-bold text-white mb-1">{courseName}</h3>
            <p className="text-sm text-violet-400 font-mono">{courseId}</p>
          </div>
          <DifficultyBadge level={courseDifficulty} />
        </div>

        <p className="text-slate-300 text-sm mb-4 leading-relaxed">{course.description}</p>

        <div className="flex items-center gap-2 mb-4 text-sm flex-wrap">
          <div className="flex items-center gap-1 text-slate-400">
            <BookOpen className="w-4 h-4" />
            <span>{courseCredits} credits</span>
          </div>
          {course.eligible !== undefined && (
            <div className={`flex items-center gap-1 ${course.eligible ? 'text-emerald-400' : 'text-rose-400'}`}>
              {course.eligible ? <Check className="w-4 h-4" /> : <X className="w-4 h-4" />}
              <span>{course.eligible ? 'Eligible' : 'Prerequisites needed'}</span>
            </div>
          )}
          <PredictedGradeBadge prediction={prediction} />
        </div>

        {course.matchReason && (
          <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg p-3 mb-3">
            <div className="flex items-start gap-2">
              <Sparkles className="w-4 h-4 text-violet-400 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-violet-200">{course.matchReason}</p>
            </div>
          </div>
        )}

        {factors.length > 0 && (
          <div className="mb-3">
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors mb-2"
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span>Why this course? ({factors.length} factor{factors.length !== 1 ? 's' : ''})</span>
            </button>
            <div className="flex flex-wrap gap-1.5">
              {visibleFactors.map((factor, i) => (
                <FactorPill key={i} factor={factor} />
              ))}
              {!expanded && factors.length > 2 && (
                <span className="inline-flex items-center px-2 py-1 text-xs text-slate-500">
                  +{factors.length - 2} more
                </span>
              )}
            </div>
          </div>
        )}

        {course.prerequisites && course.prerequisites.length > 0 && (
          <div className="text-xs text-slate-500">
            Prerequisites: {course.prerequisites.join(', ')}
          </div>
        )}
      </div>
    </div>
  );
}
