import { GraduationCap } from 'lucide-react';

const NAV_ITEMS = [
  { label: 'Home', stub: true },
  { label: 'Registration', stub: true },
  { label: 'Financial Aid', stub: true },
  { label: 'Advising', stub: true },
  { label: 'Course Planning', stub: false },
];

/**
 * University-branded chrome the advisor lives inside of. This is the piece
 * that turns "a course recommender" into "a tile in the student portal" —
 * everything below the top bar is the existing AI Course Advisor app,
 * unmodified, just no longer the whole page.
 */
export default function PortalShell({ studentName, onSignOut, children }) {
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-indigo-900 text-white">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6 min-w-0">
            <div className="flex items-center gap-2 flex-shrink-0">
              <GraduationCap className="w-5 h-5 text-amber-400" />
              <span className="font-bold text-sm tracking-tight hidden sm:inline">
                Midwestern State University
              </span>
            </div>
            <nav className="hidden md:flex items-center gap-1" aria-label="Portal">
              {NAV_ITEMS.map(({ label, stub }) => (
                <span
                  key={label}
                  title={stub ? `${label} (not part of this demo)` : undefined}
                  className={`px-3 py-1.5 rounded-md text-xs font-semibold ${
                    stub
                      ? 'text-indigo-300/70 cursor-default'
                      : 'bg-white/10 text-white'
                  }`}
                >
                  {label}
                </span>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <span className="text-xs text-indigo-200 hidden sm:inline truncate max-w-[10rem]">
              {studentName}
            </span>
            <button
              type="button"
              onClick={onSignOut}
              className="text-xs font-semibold px-3 py-1.5 rounded-md bg-white/10 hover:bg-white/20 transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
