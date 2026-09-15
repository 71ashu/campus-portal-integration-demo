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
    // A fixed h-screen column with header/footer as shrink-0 and the app in
    // a flex-1 middle band: the advisor tab sizes itself with h-screen
    // internally (unmodified from the standalone project), which would
    // otherwise overflow the viewport once a header and footer are stacked
    // around it. min-h-0 on the middle band is what lets that inner
    // h-screen content size against the *remaining* space instead of the
    // full viewport.
    <div className="h-screen flex flex-col bg-slate-100">
      <header className="bg-indigo-900 text-white flex-shrink-0">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6 min-w-0">
            <div className="flex items-center gap-2 flex-shrink-0">
              <GraduationCap className="w-5 h-5 text-amber-400" />
              <span className="font-bold text-sm tracking-tight hidden sm:inline">
                Santa Clara University
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
      <div className="flex-1 min-h-0 overflow-y-auto">
        {children}
      </div>
      <footer className="flex-shrink-0 px-4 py-2 text-center text-[11px] text-slate-400 border-t border-slate-200 bg-slate-100">
        Unofficial personal/demo project. Not affiliated with, endorsed by, or
        representing Santa Clara University. Course and program data are drawn
        from SCU's public course bulletin for demonstration purposes only.
      </footer>
    </div>
  );
}
