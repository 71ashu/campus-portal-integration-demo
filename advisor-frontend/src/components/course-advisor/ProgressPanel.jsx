import { BookOpen, GraduationCap, Calendar, Check } from 'lucide-react';

export default function ProgressPanel({ degreeProgress, progressCoursesTab, setProgressCoursesTab }) {
  if (!degreeProgress) return null;

  const progressWidth = `${degreeProgress.progressPercentage}%`;
  const creditsRemaining = Math.max((degreeProgress.requiredCredits || 0) - (degreeProgress.totalCredits || 0), 0);
  const completedCourses = degreeProgress.completedCourses || [];
  const currentCourses = degreeProgress.currentCourses || [];
  const allCourses = [...currentCourses, ...completedCourses];
  const hasDetailedCourses = completedCourses.length > 0 || currentCourses.length > 0;
  const requirementItems = degreeProgress.programRequirementItems || [];

  const renderProgressCourse = (course, idx, status) => {
    const courseId = course.courseId || course.course_id || course.id || `course-${idx}`;
    const courseName = course.courseName || course.course_name || course.name || courseId;
    const units = course.units;
    const finalLetter = course.finalLetter || course.final_letter;
    const finalScore = course.finalScore ?? course.final_score;
    const courseGPA = course.courseGPA ?? course.course_gpa ?? course.gradePoints ?? course.grade_points;
    const statusStyles =
      status === 'completed'
        ? 'border-emerald-500/30 bg-emerald-500/10'
        : 'border-amber-500/30 bg-amber-500/10';

    return (
      <div key={`${status}-${courseId}-${idx}`} className={`rounded-lg border p-3 ${statusStyles}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-white">{courseName}</div>
            <div className="text-xs text-slate-300 font-mono">{courseId}</div>
          </div>
          {typeof units === 'number' && (
            <span className="text-xs text-slate-300">{units} units</span>
          )}
        </div>
        {(finalLetter || finalScore != null || courseGPA != null) && (
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {finalLetter && (
              <span className="px-2 py-1 rounded bg-slate-800/60 border border-slate-600/50 text-slate-200">
                Grade: {finalLetter}
              </span>
            )}
            {finalScore != null && (
              <span className="px-2 py-1 rounded bg-slate-800/60 border border-slate-600/50 text-slate-200">
                Score: {finalScore}
              </span>
            )}
            {courseGPA != null && (
              <span className="px-2 py-1 rounded bg-slate-800/60 border border-slate-600/50 text-slate-200">
                Course GPA: {Number(courseGPA).toFixed(2)}
              </span>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="bg-gradient-to-br from-slate-800/80 to-slate-900/80 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <GraduationCap className="w-6 h-6 text-violet-400" />
        <div>
          <h2 className="text-2xl font-bold text-white">Degree Progress</h2>
          {degreeProgress.programName && (
            <p className="text-sm text-slate-400">
              {degreeProgress.programName}
              {degreeProgress.programDegreeType ? ` (${degreeProgress.programDegreeType})` : ''}
            </p>
          )}
        </div>
      </div>

      <div className="mb-6">
        <div className="flex justify-between items-baseline mb-2">
          <span className="text-sm text-slate-400">Overall Progress</span>
          <span className="text-2xl font-bold text-white">{degreeProgress.progressPercentage.toFixed(1)}%</span>
        </div>
        <div className="h-3 bg-slate-700/50 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full transition-all duration-1000 ease-out"
            style={{ width: progressWidth }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-slate-700/30 rounded-xl p-4 border border-slate-600/30">
          <div className="text-3xl font-bold text-white mb-1">{degreeProgress.totalCredits}</div>
          <div className="text-sm text-slate-400">Credits Earned</div>
        </div>
        <div className="bg-slate-700/30 rounded-xl p-4 border border-slate-600/30">
          <div className="text-3xl font-bold text-white mb-1">{creditsRemaining}</div>
          <div className="text-sm text-slate-400">Credits Remaining</div>
        </div>
        <div className="bg-slate-700/30 rounded-xl p-4 border border-slate-600/30">
          <div className="text-3xl font-bold text-white mb-1">{degreeProgress.majorCredits}</div>
          <div className="text-sm text-slate-400">Major Credits</div>
        </div>
        <div className="bg-slate-700/30 rounded-xl p-4 border border-slate-600/30">
          <div className="text-3xl font-bold text-white mb-1">{degreeProgress.completedCoursesCount}</div>
          <div className="text-sm text-slate-400">Courses Completed</div>
        </div>
      </div>

      {requirementItems.length > 0 && (
        <div className="mt-6 bg-slate-700/30 rounded-xl p-4 border border-slate-600/30">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">Program Requirements</h3>
          <div className="space-y-2">
            {requirementItems.map((item, idx) => (
              <div key={`${item}-${idx}`} className="text-sm text-slate-300">
                - {item}
              </div>
            ))}
          </div>
        </div>
      )}

      {hasDetailedCourses && (
        <div className="mt-6">
          <div className="flex gap-2 mb-4 bg-slate-800/50 p-1.5 rounded-xl border border-slate-700/50 w-fit">
            <button
              onClick={() => setProgressCoursesTab('current')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300 ${
                progressCoursesTab === 'current'
                  ? 'bg-amber-500/80 text-white shadow-lg shadow-amber-500/20'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <Calendar className="w-4 h-4 inline mr-2" />
              Current Courses
            </button>
            <button
              onClick={() => setProgressCoursesTab('completed')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300 ${
                progressCoursesTab === 'completed'
                  ? 'bg-emerald-500/80 text-white shadow-lg shadow-emerald-500/20'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <Check className="w-4 h-4 inline mr-2" />
              Completed Courses
            </button>
            <button
              onClick={() => setProgressCoursesTab('all')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-300 ${
                progressCoursesTab === 'all'
                  ? 'bg-violet-500/80 text-white shadow-lg shadow-violet-500/20'
                  : 'text-slate-300 hover:text-white'
              }`}
            >
              <BookOpen className="w-4 h-4 inline mr-2" />
              All Courses
            </button>
          </div>

          {progressCoursesTab === 'completed' ? (
            <div className="space-y-2">
              {completedCourses.length > 0 ? (
                completedCourses.map((course, idx) => renderProgressCourse(course, idx, 'completed'))
              ) : (
                <div className="text-sm text-slate-400">No completed courses yet.</div>
              )}
            </div>
          ) : progressCoursesTab === 'all' ? (
            <div className="space-y-2">
              {allCourses.length > 0 ? (
                allCourses.map((course, idx) => {
                  const status = (course.status || '').toLowerCase() === 'completed' ? 'completed' : 'current';
                  return renderProgressCourse(course, idx, status);
                })
              ) : (
                <div className="text-sm text-slate-400">No courses yet.</div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {currentCourses.length > 0 ? (
                currentCourses.map((course, idx) => renderProgressCourse(course, idx, 'current'))
              ) : (
                <div className="text-sm text-slate-400">No current courses.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
