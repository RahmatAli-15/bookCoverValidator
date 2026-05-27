import { Navigate, Route, Routes } from "react-router-dom";

import DashboardLayout from "./layouts/DashboardLayout";
import AirtableSyncPage from "./pages/AirtableSyncPage";
import BookDetailsPage from "./pages/BookDetailsPage";
import CustomerEmailPage from "./pages/CustomerEmailPage";
import DashboardPage from "./pages/DashboardPage";
import ReviewDashboardPage from "./pages/ReviewDashboardPage";

export default function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/customer-email" element={<CustomerEmailPage />} />
        <Route path="/airtable-sync" element={<AirtableSyncPage />} />
        <Route path="/book/:filename" element={<BookDetailsPage />} />
        <Route path="/review" element={<ReviewDashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardLayout>
  );
}
