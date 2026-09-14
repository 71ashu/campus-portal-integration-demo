import { useState } from 'react';
import { GraduationCap } from 'lucide-react';
import { api } from '../api';

const DEMO_STUDENTS = [
  { sisId: 'M00412771', name: 'Jordan Rivera', note: 'Junior · mid-way through the CS core' },
  { sisId: 'M00298841', name: 'Avery Chen', note: 'Sophomore · just getting started' },
];

export default function PortalLogin({ onAuthenticated }) {
  const [sisId, setSisId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const submit = async (id) => {
    const value = (id || sisId).trim();
    if (!value) return;
    setError('');
    setLoading(true);
    try {
      const { student } = await api.ssoLogin(value);
      onAuthenticated(student);
    } catch (err) {
      setError(err.message || 'Could not sign in.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-indigo-900 flex items-center justify-center mb-3">
            <GraduationCap className="w-7 h-7 text-amber-400" />
          </div>
          <h1 className="text-lg font-bold text-slate-900">Midwestern State University</h1>
          <p className="text-sm text-slate-500">Student Portal</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
            Sign in with your University ID
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
            className="space-y-3"
          >
            <input
              type="text"
              value={sisId}
              onChange={(e) => setSisId(e.target.value)}
              placeholder="e.g. M00412771"
              className="w-full px-3 py-2.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autoFocus
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-indigo-900 text-white text-sm font-semibold hover:bg-indigo-800 disabled:opacity-60 transition-colors"
            >
              {loading ? 'Signing in…' : 'Continue'}
            </button>
          </form>

          <p className="text-[11px] text-slate-400 mt-3 leading-snug">
            In production this screen is your campus SSO / LTI launch — no password ever
            touches this app. For the demo, pick one of the seeded students below.
          </p>

          <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
            {DEMO_STUDENTS.map((s) => (
              <button
                key={s.sisId}
                type="button"
                onClick={() => submit(s.sisId)}
                disabled={loading}
                className="w-full text-left px-3 py-2 rounded-lg border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors"
              >
                <p className="text-sm font-semibold text-slate-800">{s.name} <span className="font-normal text-slate-400">· {s.sisId}</span></p>
                <p className="text-xs text-slate-500">{s.note}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
