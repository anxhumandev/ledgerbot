import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate, RouterProvider, useParams, useRouteError } from "react-router-dom";
import AppShell, { PageFallback } from "../layouts/AppShell";
import { ErrorState } from "../ui/core";

const page = (load: () => Promise<{ default: React.ComponentType<any> }>) => lazy(load);
const Overview = page(() => import("../pages/OverviewPage"));
const Inventory = page(() => import("../pages/InventoryPage"));
const InventoryDetail = page(() => import("../pages/InventoryDetailPage"));
const MatchReview = page(() => import("../pages/MatchReviewPage"));
const Clusters = page(() => import("../pages/ClustersPage"));
const Policies = page(() => import("../pages/PoliciesPage"));
const Suppliers = page(() => import("../pages/SuppliersPage"));
const SupplierDetail = page(() => import("../pages/SupplierDetailPage"));
const Ingestion = page(() => import("../pages/IngestionPage"));
const Offers = page(() => import("../pages/OfferComparisonPage"));
const Optimization = page(() => import("../pages/OfferOptimizationPage"));
const RankingPreview = page(() => import("../pages/RankingPreviewPage"));
const Experiments = page(() => import("../pages/RankingExperimentsPage"));
const Analytics = page(() => import("../pages/AnalyticsPage"));
const Audit = page(() => import("../pages/AuditPage"));
const SettingsPage = page(() => import("../pages/SettingsPage"));

function RouteError() {
  const e = useRouteError();
  return <div className="p-8"><ErrorState error={e} onRetry={() => window.location.reload()} /></div>;
}

function NotFound() {
  return <ErrorState error={{ code: "not_found", message: "This page does not exist. Use the navigation or Ctrl K to find what you need." }} />;
}

function InventoryKind() {
  const { kind } = useParams();
  if (kind !== "hotels" && kind !== "sightseeing") return <NotFound />;
  return <Inventory key={kind} kind={kind === "hotels" ? "hotel" : "activity"} />;
}

const router = createBrowserRouter([
  {
    path: "/", element: <AppShell />, errorElement: <RouteError />, children: [
      { index: true, element: <Navigate to="/overview" replace /> },
      { path: "overview", element: <Overview /> },
      { path: "inventory", element: <Navigate to="/inventory/hotels" replace /> },
      { path: "inventory/:kind", element: <InventoryKind /> },
      { path: "inventory/:type/:id", element: <InventoryDetail /> },
      { path: "matching", element: <Navigate to="/matching/review" replace /> },
      { path: "matching/review", element: <MatchReview /> },
      { path: "matching/clusters", element: <Clusters /> },
      { path: "matching/policies", element: <Policies /> },
      { path: "suppliers", element: <Navigate to="/suppliers/directory" replace /> },
      { path: "suppliers/directory", element: <Suppliers /> },
      { path: "suppliers/ingestion", element: <Ingestion /> },
      { path: "suppliers/:id", element: <SupplierDetail /> },
      { path: "offers", element: <Navigate to="/offers/comparison" replace /> },
      { path: "offers/comparison", element: <Offers /> },
      { path: "offers/optimization", element: <Optimization /> },
      { path: "ranking", element: <Navigate to="/ranking/preview" replace /> },
      { path: "ranking/preview", element: <RankingPreview /> },
      { path: "ranking/experiments", element: <Experiments /> },
      { path: "analytics", element: <Analytics /> },
      { path: "audit", element: <Audit /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export default function App() {
  return <Suspense fallback={<PageFallback />}><RouterProvider router={router} /></Suspense>;
}
