import { createBrowserRouter, Navigate } from "react-router";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppLayout from "@/layouts/AppLayout";
import Analytics from "@/pages/Analytics";
import Dashboard from "@/pages/Dashboard";
import InvestigationDetail from "@/pages/InvestigationDetail";
import InvestigationsDashboard from "@/pages/InvestigationsDashboard";
import Login from "@/pages/Login";
import NewInvestigation from "@/pages/NewInvestigation";
import Register from "@/pages/Register";
import Reports from "@/pages/Reports";
import Settings from "@/pages/Settings";

export const router = createBrowserRouter([
  { path: "/login", Component: Login },
  { path: "/register", Component: Register },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", Component: Dashboard },
      { path: "investigations", Component: InvestigationsDashboard },
      { path: "investigations/new", Component: NewInvestigation },
      { path: "investigations/:id", Component: InvestigationDetail },
      { path: "analytics", Component: Analytics },
      { path: "reports", Component: Reports },
      { path: "settings", Component: Settings },
      { path: "*", element: <Navigate to="/dashboard" replace /> },
    ],
  },
]);
