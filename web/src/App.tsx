import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/Toast";
import { AuctionPage } from "./pages/AuctionPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EntrustmentPage } from "./pages/EntrustmentPage";
import { LoginPage } from "./pages/LoginPage";
import { LookupPage } from "./pages/LookupPage";
import { ManagePage } from "./pages/ManagePage";
import { PrintPage } from "./pages/PrintPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RacingPage } from "./pages/RacingPage";

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/dashboard" element={<Navigate to="/" replace />} />
              <Route path="/main" element={<LookupPage />} />
              <Route path="/manage" element={<ManagePage />} />
              <Route path="/print" element={<PrintPage />} />
              <Route path="/entrustment" element={<EntrustmentPage />} />
              <Route path="/auction" element={<AuctionPage />} />
              <Route path="/racing" element={<RacingPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/login" element={<LoginPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
