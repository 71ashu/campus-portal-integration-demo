import { Target, Brain, Check, Calendar } from 'lucide-react';

export default function ProfilePanel({ studentProfile }) {
  return (
    <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-6 space-y-6">
      <div className="flex items-center gap-4">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-2xl font-bold text-white">
          {studentProfile.name.split(' ').map((n) => n[0]).join('')}
        </div>
        <div>
          <h2 className="text-2xl font-bold text-white">{studentProfile.name}</h2>
          <p className="text-slate-400">{studentProfile.year} • {studentProfile.major}</p>
          <p className="text-slate-500 text-sm">{studentProfile.university} • {studentProfile.program}</p>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-violet-400" />
            <h3 className="text-sm font-semibold text-slate-300">Career Goals</h3>
          </div>
          <p className="text-slate-400 text-sm">{studentProfile.careerGoals}</p>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-4 h-4 text-violet-400" />
            <h3 className="text-sm font-semibold text-slate-300">Interests</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {studentProfile.interests.map((interest, idx) => (
              <span key={idx} className="px-3 py-1 bg-violet-500/20 border border-violet-500/30 rounded-full text-xs text-violet-300">
                {interest}
              </span>
            ))}
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-2">
            <Check className="w-4 h-4 text-violet-400" />
            <h3 className="text-sm font-semibold text-slate-300">Completed Courses</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {studentProfile.completedCourses.map((course, idx) => (
              <span key={idx} className="px-2 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded text-xs text-emerald-300 font-mono">
                {course}
              </span>
            ))}
          </div>
        </div>

        {studentProfile.currentCourses && studentProfile.currentCourses.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-violet-400" />
              <h3 className="text-sm font-semibold text-slate-300">Current Courses</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {studentProfile.currentCourses.map((course, idx) => (
                <span key={idx} className="px-2 py-1 bg-amber-500/10 border border-amber-500/20 rounded text-xs text-amber-300 font-mono">
                  {course}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
