import { Award, BookOpen, Calendar, GraduationCap, Target } from 'lucide-react';

function StatCard({ label, value, hint }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
      <div className="text-3xl font-bold text-white mb-1">{value}</div>
      <div className="text-sm text-slate-400">{label}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  );
}

function courseLabel(course, idx) {
  return course.courseId || course.course_id || course.id || `course-${idx}`;
}

function courseName(course, idx) {
  return course.courseName || course.course_name || course.name || courseLabel(course, idx);
}

export default function DashboardPanel({ studentProfile, degreeProgress, onAskAdvisor }) {
  if (!degreeProgress) {
    return (
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-8 text-slate-400">
        Loading your progress…
      </div>
    );
  }

  const progressPct = degreeProgress.progressPercentage ?? 0;
  const creditsRemaining = Math.max(
    (degreeProgress.requiredCredits || 0) - (degreeProgress.totalCredits || 0),
    0
  );
  const gpa = degreeProgress.programGPA;
  const currentCourses = degreeProgress.currentCourses || [];
  const requirementItems = degreeProgress.programRequirementItems || [];
  const firstName = (studentProfile?.name || 'there').split(' ')[0];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-black text-white">Welcome back, {firstName}</h2>
        <p className="text-slate-400 mt-1">
          {degreeProgress.programName || studentProfile?.program || 'Your program'}
          {degreeProgress.programDegreeType ? ` · ${degreeProgress.programDegreeType}` : ''}
          {studentProfile?.year ? ` · ${studentProfile.year}` : ''}
        </p>
      </div>

      <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 border border-slate-700/50 rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <GraduationCap className="w-6 h-6 text-violet-400" />
          <h3 className="text-lg font-bold text-white">Overall progress</h3>
        </div>
        <div className="flex justify-between items-baseline mb-2">
          <span className="text-sm text-slate-400">Degree completion</span>
          <span className="text-2xl font-bold text-white">{Number(progressPct).toFixed(1)}%</span>
        </div>
        <div className="h-3 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full transition-all duration-1000 ease-out"
            style={{ width: `${Math.min(Math.max(progressPct, 0), 100)}%` }}
          />
        </div>
        <p className="text-xs text-slate-500 mt-2">
          {degreeProgress.totalCredits || 0} of {degreeProgress.requiredCredits || 0} required credits
        </p>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Program GPA"
          value={gpa != null ? Number(gpa).toFixed(2) : '—'}
          hint="Across completed courses"
        />
        <StatCard label="Credits earned" value={degreeProgress.totalCredits ?? 0} />
        <StatCard label="Credits remaining" value={creditsRemaining} />
        <StatCard label="Courses completed" value={degreeProgress.completedCoursesCount ?? 0} />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <section className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Calendar className="w-4 h-4 text-amber-400" />
            <h3 className="font-semibold text-white">Current courses</h3>
          </div>
          {currentCourses.length === 0 ? (
            <p className="text-sm text-slate-400">No courses in progress.</p>
          ) : (
            <ul className="space-y-2">
              {currentCourses.map((course, idx) => (
                <li
                  key={`${courseLabel(course, idx)}-${idx}`}
                  className="flex items-start justify-between gap-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2.5"
                >
                  <div>
                    <div className="text-sm font-semibold text-white">{courseName(course, idx)}</div>
                    <div className="text-xs text-slate-400 font-mono">{courseLabel(course, idx)}</div>
                  </div>
                  {typeof course.units === 'number' && (
                    <span className="text-xs text-slate-300 whitespace-nowrap">{course.units} units</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-violet-400" />
            <h3 className="font-semibold text-white">Program requirements</h3>
          </div>
          {requirementItems.length === 0 ? (
            <p className="text-sm text-slate-400">No requirement details available yet.</p>
          ) : (
            <ul className="space-y-2">
              {requirementItems.map((item, idx) => (
                <li key={`${item}-${idx}`} className="text-sm text-slate-300 flex gap-2">
                  <Award className="w-4 h-4 text-violet-400 flex-shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onAskAdvisor}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold bg-gradient-to-r from-violet-500 to-fuchsia-500 hover:from-violet-600 hover:to-fuchsia-600 shadow-lg shadow-violet-500/30 transition-all"
        >
          <BookOpen className="w-4 h-4" />
          Plan next semester
        </button>
        <p className="text-sm text-slate-500">Ask the advisor for courses that keep you on track.</p>
      </div>
    </div>
  );
}
