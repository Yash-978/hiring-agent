import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AppLayout } from "./routes/AppLayout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Login } from "./pages/Login";
import { Candidates } from "./pages/Candidates";
import { CandidateDetail } from "./pages/CandidateDetail";
import { JobCompare } from "./pages/JobCompare";
import { Approvals } from "./pages/Approvals";
import { Jobs } from "./pages/Jobs";

export function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/candidates" element={<Candidates />} />
            <Route path="/candidates/:id" element={<CandidateDetail />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/jobs/:id/compare" element={<JobCompare />} />
            <Route path="/approvals" element={<Approvals />} />
          </Route>
        </Route>
        <Route path="/" element={<Navigate to="/candidates" replace />} />
        <Route path="*" element={<Navigate to="/candidates" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}