import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppLayout } from './components/AppLayout';

// Pages
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { ForgotPassword } from './pages/ForgotPassword';
import { ResetPassword } from './pages/ResetPassword';

import { Dashboard } from './pages/Dashboard';
import { Applications } from './pages/Applications';
import { NewConsent } from './pages/NewConsent';
import { ConsentDetail } from './pages/ConsentDetail';
import { AddEvidence } from './pages/AddEvidence';
import { AnalysisDetail } from './pages/AnalysisDetail';
import { Alerts } from './pages/Alerts';
import { Drafts } from './pages/Drafts';
import { Analytics } from './pages/Analytics';
import { Evaluation } from './pages/Evaluation';
import { Settings } from './pages/Settings';

// Route Guard for Authenticated Views
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B0F19] flex items-center justify-center text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
          <span className="text-xs font-medium">Verifying privacy session...</span>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};

// Route Guard for Anonymous Only Views (e.g. Login, Register)
const RequireAnon: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Landing & Simulator */}
          <Route path="/" element={<Landing />} />

          {/* Authentication Routes (Anon only) */}
          <Route
            path="/login"
            element={
              <RequireAnon>
                <Login />
              </RequireAnon>
            }
          />
          <Route
            path="/register"
            element={
              <RequireAnon>
                <Register />
              </RequireAnon>
            }
          />
          <Route
            path="/forgot-password"
            element={
              <RequireAnon>
                <ForgotPassword />
              </RequireAnon>
            }
          />
          <Route
            path="/reset-password"
            element={
              <RequireAnon>
                <ResetPassword />
              </RequireAnon>
            }
          />

          {/* Protected Application Workspace Layout */}
          <Route
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/consents" element={<Applications />} />
            <Route path="/consents/new" element={<NewConsent />} />
            <Route path="/consents/:id" element={<ConsentDetail />} />
            <Route path="/evidence/new" element={<AddEvidence />} />
            <Route path="/analyses/:id" element={<AnalysisDetail />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/drafts" element={<Drafts />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/settings" element={<Settings />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
