import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from './api';
import CourseAdvisor from './CourseAdvisor';
import PortalShell from './portal/PortalShell';
import PortalLogin from './portal/PortalLogin';

export default function App() {
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me()
      .then(({ student }) => setStudent(student))
      .catch(() => setStudent(null))
      .finally(() => setLoading(false));
  }, []);

  const handleLogout = async () => {
    await api.logout();
    setStudent(null);
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-800 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!student) {
    return <PortalLogin onAuthenticated={setStudent} />;
  }

  return (
    <PortalShell studentName={student.name} onSignOut={handleLogout}>
      <CourseAdvisor student={student} onLogout={handleLogout} onProfileUpdate={setStudent} />
    </PortalShell>
  );
}
