import { useEffect, useRef, useState } from 'react';
import { MessageSquarePlus, Pencil, Trash2, X } from 'lucide-react';

function timeLabel(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  const diffMs = Date.now() - then.getTime();
  const day = 24 * 60 * 60 * 1000;
  if (diffMs < day && then.getDate() === new Date().getDate()) {
    return then.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }
  if (diffMs < 7 * day) {
    return then.toLocaleDateString([], { weekday: 'short' });
  }
  return then.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export default function ConversationList({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation = () => {},
  onCloseMobile,
}) {
  const [pendingDelete, setPendingDelete] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState('');
  const editRef = useRef(null);

  useEffect(() => {
    if (editingId != null) {
      editRef.current?.focus();
      editRef.current?.select();
    }
  }, [editingId]);

  const startRename = (c) => {
    setPendingDelete(null);
    setDraft(c.title || '');
    setEditingId(c.id);
  };

  const commitRename = () => {
    const id = editingId;
    setEditingId(null);
    const clean = draft.trim();
    const original = conversations.find((c) => c.id === id);
    if (clean && original && clean !== original.title) {
      onRenameConversation(id, clean);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-3 pt-4 pb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Conversations
        </span>
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="lg:hidden p-1 text-slate-400 hover:text-white"
            aria-label="Close conversations"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="px-3 pb-3">
        <button
          type="button"
          onClick={onNewConversation}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-semibold text-white bg-violet-500 hover:bg-violet-400 shadow-lg shadow-violet-500/20 transition-colors"
        >
          <MessageSquarePlus className="w-4 h-4" />
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
        {conversations.length === 0 && (
          <p className="px-3 py-2 text-xs text-slate-500">No conversations yet.</p>
        )}
        {conversations.map((c) => {
          const active = c.id === activeConversationId;

          if (editingId === c.id) {
            return (
              <div key={c.id} className="rounded-lg bg-slate-800 px-2 py-1.5">
                <input
                  ref={editRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      commitRename();
                    } else if (e.key === 'Escape') {
                      setEditingId(null);
                    }
                  }}
                  onBlur={commitRename}
                  maxLength={200}
                  className="w-full rounded-md border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-white focus:border-violet-500 focus:outline-none"
                />
              </div>
            );
          }

          return (
            <div
              key={c.id}
              className={`group relative rounded-lg transition-colors ${
                active ? 'bg-slate-800' : 'hover:bg-slate-800/60'
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectConversation(c.id)}
                onDoubleClick={() => startRename(c)}
                className="w-full text-left px-3 py-2 pr-14"
              >
                <span
                  className={`block truncate text-sm ${
                    active ? 'text-white font-medium' : 'text-slate-300'
                  }`}
                >
                  {c.title || 'New conversation'}
                </span>
                <span className="block text-[11px] text-slate-500">{timeLabel(c.updatedAt)}</span>
              </button>

              {pendingDelete === c.id ? (
                <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      onDeleteConversation(c.id);
                      setPendingDelete(null);
                    }}
                    className="text-[11px] px-1.5 py-0.5 rounded bg-red-500/80 text-white hover:bg-red-500"
                  >
                    Delete
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(null)}
                    className="text-[11px] px-1.5 py-0.5 rounded bg-slate-700 text-slate-200 hover:bg-slate-600"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
                  <button
                    type="button"
                    onClick={() => startRename(c)}
                    className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-slate-700/60"
                    aria-label={`Rename conversation ${c.title || ''}`}
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(c.id)}
                    className="p-1 rounded text-slate-500 hover:text-red-400 hover:bg-slate-700/60"
                    aria-label={`Delete conversation ${c.title || ''}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
