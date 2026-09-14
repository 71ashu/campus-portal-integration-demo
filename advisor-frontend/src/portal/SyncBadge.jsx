import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';

function timeAgo(iso) {
  if (!iso) return 'never';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

/**
 * Provenance strip: makes it visible that this data came from the SIS (not
 * from something the student typed in) and lets the demo trigger a manual
 * re-pull after the registrar posts a grade, without waiting for the
 * background poll.
 */
export default function SyncBadge({ syncedAt, refreshing, onRefresh }) {
  const [, forceTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => forceTick((n) => n + 1), 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-slate-800/50 border border-slate-700/40 text-xs">
      <span className="text-slate-400">
        <span className="text-slate-300 font-semibold">Synced from SIS</span> · {timeAgo(syncedAt)}
      </span>
      <button
        type="button"
        onClick={onRefresh}
        disabled={refreshing}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-slate-300 bg-slate-700/60 hover:bg-slate-700 disabled:opacity-60 transition-colors"
      >
        <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
        {refreshing ? 'Syncing…' : 'Refresh from SIS'}
      </button>
    </div>
  );
}
