import { LayoutDashboard, LogOut, Menu, MessageSquare, TrendingUp, User, X } from 'lucide-react';

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'advisor', label: 'Ask Advisor', icon: MessageSquare },
  { id: 'progress', label: 'Courses', icon: TrendingUp },
  { id: 'profile', label: 'Profile', icon: User },
];

export default function AppSidebar({
  studentProfile,
  degreeProgress,
  activeTab,
  onNavigate,
  onLogout,
  mobileOpen,
  onCloseMobile,
  onOpenMobile,
}) {
  const initials = (studentProfile?.name || '?')
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const progressPct = degreeProgress?.progressPercentage ?? 0;
  const gpa = degreeProgress?.programGPA;

  const sidebarBody = (
    <>
      <div className="px-5 pt-6 pb-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-violet-300/80">AI Course Advisor</p>
        <h1 className="mt-1 text-lg font-black leading-tight bg-gradient-to-r from-violet-400 via-fuchsia-400 to-violet-400 bg-clip-text text-transparent">
          Academic Hub
        </h1>
      </div>

      <nav className="flex-1 px-3 space-y-1" aria-label="Main">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => {
                onNavigate(id);
                onCloseMobile();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                active
                  ? 'bg-violet-500 text-white shadow-lg shadow-violet-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/80'
              }`}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </button>
          );
        })}
      </nav>

      <div className="px-4 pb-3">
        <div className="rounded-xl border border-slate-700/60 bg-slate-800/50 p-3">
          <div className="flex justify-between items-baseline mb-1.5">
            <span className="text-xs text-slate-400">Degree progress</span>
            <span className="text-sm font-bold text-white">{Number(progressPct).toFixed(1)}%</span>
          </div>
          <div className="h-1.5 bg-slate-700/70 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full"
              style={{ width: `${Math.min(Math.max(progressPct, 0), 100)}%` }}
            />
          </div>
          {gpa != null && (
            <p className="mt-2 text-xs text-slate-400">
              GPA <span className="text-slate-200 font-semibold">{Number(gpa).toFixed(2)}</span>
            </p>
          )}
        </div>
      </div>

      <div className="px-4 pb-5 pt-1 border-t border-slate-800">
        <div className="flex items-center gap-3 mb-3 px-1">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-xs font-bold flex-shrink-0">
            {initials}
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white truncate">{studentProfile?.name}</p>
            <p className="text-xs text-slate-500 truncate">{studentProfile?.program || studentProfile?.major}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-300 bg-slate-800/70 hover:bg-slate-700/70 border border-slate-700/50 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </>
  );

  return (
    <>
      <button
        type="button"
        onClick={onOpenMobile}
        className="lg:hidden fixed top-4 left-4 z-40 p-2 rounded-lg bg-slate-800/90 border border-slate-700/60 text-white"
        aria-label="Open navigation"
      >
        <Menu className="w-5 h-5" />
      </button>

      {mobileOpen && (
        <button
          type="button"
          className="lg:hidden fixed inset-0 z-40 bg-black/60"
          aria-label="Close navigation"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed lg:sticky top-0 left-0 z-50 h-screen w-64 flex flex-col border-r border-slate-800 bg-slate-950/95 backdrop-blur-md transition-transform duration-200 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <button
          type="button"
          onClick={onCloseMobile}
          className="lg:hidden absolute top-4 right-3 p-1.5 text-slate-400 hover:text-white"
          aria-label="Close navigation"
        >
          <X className="w-5 h-5" />
        </button>
        {sidebarBody}
      </aside>
    </>
  );
}
