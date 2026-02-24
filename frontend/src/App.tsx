import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { AppLayout } from "@/components/layout/AppLayout";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { PapersPage } from "@/pages/PapersPage";
import { DraftsPage } from "@/pages/DraftsPage";
import { DraftEditor } from "@/pages/DraftEditor";
import { WorkspaceMembersPage } from "@/pages/WorkspaceMembersPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { AdminPage } from "@/pages/AdminPage";
import { Toaster } from "sonner";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes */}
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/workspace/:workspaceId/papers" element={<PapersPage />} />
            <Route path="/workspace/:workspaceId/drafts" element={<DraftsPage />} />
            <Route path="/workspace/:workspaceId/drafts/:draftId" element={<DraftEditor />} />
            <Route path="/workspace/:workspaceId/members" element={<WorkspaceMembersPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#232323",
            border: "1px solid #333333",
            color: "#EDEDED",
          },
        }}
      />
    </AuthProvider>
  );
}

export default App;
