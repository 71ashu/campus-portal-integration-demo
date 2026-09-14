import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from './api';
import AdvisorTab from './components/course-advisor/AdvisorTab';
import AppSidebar from './components/course-advisor/AppSidebar';
import DashboardPanel from './components/course-advisor/DashboardPanel';
import ProfilePanel from './components/course-advisor/ProfilePanel';
import ProgressPanel from './components/course-advisor/ProgressPanel';
import SyncBadge from './portal/SyncBadge';

const KNOWN_TABS = ['dashboard', 'advisor', 'progress', 'profile'];
// How often to poll the SIS-backed progress endpoint for a newer `sisSyncedAt`
// while the tab is open. A real deployment would push this over a webhook +
// SSE/websocket instead of polling; short polling gets the same "the record
// changed while you were looking at it" effect with far less plumbing.
const SIS_POLL_INTERVAL_MS = 8000;

export default function CourseAdvisor({ student, onLogout }) {
  const location = useLocation();
  const navigate = useNavigate();

  const segments = location.pathname.split('/').filter(Boolean);
  const firstSegment = segments[0] || '';
  const activeTab = KNOWN_TABS.includes(firstSegment) ? firstSegment : 'dashboard';
  const routeConversationId = activeTab === 'advisor' && segments[1] ? segments[1] : null;

  const [studentProfile, setStudentProfile] = useState(student);
  const [query, setQuery] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [degreeProgress, setDegreeProgress] = useState(null);
  const [progressCoursesTab, setProgressCoursesTab] = useState('current');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const lastSeenSyncRef = useRef(null);
  const activeTabRef = useRef(activeTab);
  const activeConversationIdRef = useRef(activeConversationId);
  const chatHistoryRef = useRef(chatHistory);
  activeTabRef.current = activeTab;
  activeConversationIdRef.current = activeConversationId;
  chatHistoryRef.current = chatHistory;

  useEffect(() => {
    setStudentProfile(student);
  }, [student]);

  useEffect(() => {
    loadDegreeProgress();
    loadConversations();
  }, [studentProfile?.id]);

  // Normalize unknown paths (e.g. "/") to the dashboard.
  useEffect(() => {
    if (!KNOWN_TABS.includes(firstSegment)) {
      navigate('/dashboard', { replace: true });
    }
  }, [firstSegment, navigate]);

  // Load (or clear) the advisor conversation based on the URL.
  useEffect(() => {
    if (activeTab !== 'advisor') return undefined;

    if (!routeConversationId) {
      setActiveConversationId(null);
      setChatHistory([]);
      setConversationLoading(false);
      return undefined;
    }

    if (routeConversationId === activeConversationId) return undefined;

    let cancelled = false;
    setConversationLoading(true);
    api.getConversation(routeConversationId)
      .then(({ conversation }) => {
        if (cancelled) return;
        setChatHistory(
          (conversation.messages || []).map(({ role, content, recommendations }) => ({
            role,
            content,
            recommendations: recommendations || [],
          })),
        );
        setActiveConversationId(conversation.id);
      })
      .catch(() => {
        if (!cancelled) setChatHistory([]);
      })
      .finally(() => {
        if (!cancelled) setConversationLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // activeConversationId is intentionally excluded: it is set inside this effect
    // and re-running on that change would wipe an in-progress new conversation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, routeConversationId]);

  // Poll for SIS updates (e.g. a registrar posting a grade) and refresh the
  // open advisor conversation the moment the record actually changes,
  // instead of on a fixed timer regardless of whether anything happened.
  useEffect(() => {
    const interval = setInterval(async () => {
      const progress = await api.getProgress().catch(() => null);
      if (!progress) return;
      setDegreeProgress(progress);

      const latest = progress.sisSyncedAt;
      const previous = lastSeenSyncRef.current;
      if (latest && previous && latest !== previous) {
        refreshAfterSisUpdate();
      }
      lastSeenSyncRef.current = latest;
    }, SIS_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studentProfile?.id]);

  const loadDegreeProgress = async () => {
    try {
      const progress = await api.getProgress();
      setDegreeProgress(progress);
      lastSeenSyncRef.current = progress.sisSyncedAt;
      // Keep the Profile tab's completed/current course lists (drawn from
      // the student record, not degreeProgress) from going stale after a sync.
      const { student: refreshed } = await api.me();
      setStudentProfile(refreshed);
    } catch {
      setDegreeProgress(null);
    }
  };

  const loadConversations = async () => {
    try {
      const { conversations: rows } = await api.listConversations();
      setConversations(rows || []);
    } catch {
      setConversations([]);
    }
  };

  // Re-runs the last question asked (or a sensible default) against
  // /api/recommend so a change in the student's SIS record — a newly
  // completed prerequisite, an updated GPA — is reflected in the
  // recommendations without the student re-typing anything.
  //
  // sync_student() on the backend stamps a fresh sisSyncedAt on every call,
  // whether or not anything in the record actually changed, so both the
  // background poll and a manual "Refresh from SIS" click can independently
  // decide a refresh is warranted within moments of each other (e.g. right
  // after a registrar posts a grade). The cooldown below collapses that into
  // a single chat update instead of two near-identical ones.
  const lastRefreshAtRef = useRef(0);
  const refreshAfterSisUpdate = async () => {
    if (activeTabRef.current !== 'advisor') return;
    if (Date.now() - lastRefreshAtRef.current < 5000) return;
    lastRefreshAtRef.current = Date.now();

    const lastUserTurn = [...chatHistoryRef.current].reverse().find((m) => m.role === 'user');
    const q = lastUserTurn?.content || 'What courses should I take next?';

    try {
      const { recommendations: recs, message, conversationId } = await api.getRecommendations(q, {
        conversationId: activeConversationIdRef.current,
        history: [],
      });
      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', content: `🔄 Your academic record just updated at the SIS. ${message}`, recommendations: recs },
      ]);
      if (conversationId && conversationId !== activeConversationIdRef.current) {
        setActiveConversationId(conversationId);
        navigate(`/advisor/${conversationId}`, { replace: true });
      }
      loadConversations();
    } catch {
      // Silent: this is a background refresh, not a user-initiated action.
    }
  };

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      await api.syncFromSis();
      await loadDegreeProgress();
      await refreshAfterSisUpdate();
    } finally {
      setSyncing(false);
    }
  };

  const handleNavigate = (tab) => {
    setMobileNavOpen(false);
    if (tab === 'advisor' && activeConversationId) {
      navigate(`/advisor/${activeConversationId}`);
      return;
    }
    navigate(`/${tab}`);
  };

  const handleSelectConversation = (id) => {
    setMobileNavOpen(false);
    navigate(`/advisor/${id}`);
  };

  const handleNewConversation = () => {
    setQuery('');
    setMobileNavOpen(false);
    navigate('/advisor');
  };

  const handleRenameConversation = async (id, title) => {
    const clean = (title || '').trim();
    if (!clean) return;
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: clean } : c)),
    );
    try {
      await api.renameConversation(id, clean);
    } catch {
      loadConversations();
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
    } catch {
      // ignore; refresh below reflects real state
    }
    if (id === activeConversationId) {
      setActiveConversationId(null);
      setChatHistory([]);
      if (activeTab === 'advisor') navigate('/advisor');
    }
    loadConversations();
  };

  const handleAskAdvisor = async () => {
    if (!query.trim()) return;

    const userMessage = { role: 'user', content: query };
    const priorTurns = chatHistory
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map(({ role, content }) => ({ role, content }));
    setChatHistory((prev) => [...prev, userMessage]);
    setQuery('');
    setIsLoading(true);

    try {
      const { recommendations: recs, message, conversationId } = await api.getRecommendations(query, {
        conversationId: activeConversationId,
        history: priorTurns,
      });

      const aiMessage = {
        role: 'assistant',
        content: message,
        recommendations: recs
      };

      setChatHistory((prev) => [...prev, aiMessage]);
      if (conversationId && conversationId !== activeConversationId) {
        setActiveConversationId(conversationId);
        navigate(`/advisor/${conversationId}`, { replace: true });
      }
      loadConversations();
    } catch {
      const errorMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      };
      setChatHistory((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAskAdvisor();
    }
  };

  const goToAdvisorWithPrompt = (prompt) => {
    setQuery(prompt);
    setMobileNavOpen(false);
    navigate(activeConversationId ? `/advisor/${activeConversationId}` : '/advisor');
  };

  return (
    <div className="min-h-screen bg-app-shell text-white font-sans flex">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-fuchsia-600/10 rounded-full blur-3xl animate-pulse delay-1000" />
      </div>

      <AppSidebar
        studentProfile={studentProfile}
        degreeProgress={degreeProgress}
        activeTab={activeTab}
        onNavigate={handleNavigate}
        onLogout={onLogout}
        mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)}
        onOpenMobile={() => setMobileNavOpen(true)}
      />

      <main
        className={`relative z-10 flex-1 min-h-screen min-w-0 flex flex-col ${
          activeTab === 'advisor' ? 'overflow-hidden h-screen' : 'overflow-y-auto'
        }`}
      >
        <div className={activeTab === 'advisor' ? 'px-4 pt-4 flex-shrink-0' : 'max-w-6xl mx-auto w-full px-6 pt-16 lg:px-10 lg:pt-10'}>
          <SyncBadge
            syncedAt={degreeProgress?.sisSyncedAt}
            refreshing={syncing}
            onRefresh={handleManualSync}
          />
        </div>

        {activeTab === 'advisor' ? (
          <div className="flex-1 min-h-0 flex flex-col">
            <AdvisorTab
              chatHistory={chatHistory}
              isLoading={isLoading}
              query={query}
              setQuery={setQuery}
              handleKeyPress={handleKeyPress}
              handleAskAdvisor={handleAskAdvisor}
              conversations={conversations}
              activeConversationId={activeConversationId}
              activeConversation={conversations.find((c) => c.id === activeConversationId) || null}
              conversationLoading={conversationLoading}
              onSelectConversation={handleSelectConversation}
              onNewConversation={handleNewConversation}
              onDeleteConversation={handleDeleteConversation}
              onRenameConversation={handleRenameConversation}
            />
          </div>
        ) : (
          <div className="max-w-6xl mx-auto w-full px-6 pb-10 lg:px-10">
            {activeTab === 'dashboard' && (
              <DashboardPanel
                studentProfile={studentProfile}
                degreeProgress={degreeProgress}
                onAskAdvisor={() => goToAdvisorWithPrompt('What courses should I take next semester?')}
              />
            )}

            {activeTab === 'progress' && (
              <ProgressPanel
                degreeProgress={degreeProgress}
                progressCoursesTab={progressCoursesTab}
                setProgressCoursesTab={setProgressCoursesTab}
              />
            )}

            {activeTab === 'profile' && (
              <ProfilePanel studentProfile={studentProfile} />
            )}
          </div>
        )}
      </main>
    </div>
  );
}
