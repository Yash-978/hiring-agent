import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AppLayout } from "./routes/AppLayout";
import { Login } from "./pages/Login";
import { Candidates } from "./pages/Candidates";
import { CandidateDetail } from "./pages/CandidateDetail";
import { ApprovalsPage } from "./pages/ApprovalsPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/candidates/:id" element={<CandidateDetail />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/candidates" replace />} />
      <Route path="*" element={<Navigate to="/candidates" replace />} />
    </Routes>
  );
}