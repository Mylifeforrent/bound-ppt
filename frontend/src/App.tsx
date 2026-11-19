import { Component, type ErrorInfo, type ReactNode, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { LoginPage } from "@/pages/LoginPage";
import { HomePage } from "@/pages/HomePage";
import { IntakePage } from "@/pages/IntakePage";
import { ResearchPage } from "@/pages/ResearchPage";
import { OutlinePage } from "@/pages/OutlinePage";
import { PlanPage } from "@/pages/PlanPage";
import { StylePage } from "@/pages/StylePage";
import { DesignPage } from "@/pages/DesignPage";
import { ProjectLayout, RequireSession } from "@/pages/ProjectLayout";
import { NotFoundPage, StageRedirect } from "@/pages/StageRedirect";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 5_000,
    },
    mutations: { retry: 0 },
  },
});

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("route error", error, info.componentStack);
  }
  render() {
    if (this.state.error) {
      return (
        <div className="grid min-h-screen place-items-center px-4">
          <div className="app-card max-w-lg p-6">
            <h1 className="text-lg font-bold text-ink">This screen failed to render</h1>
            <p className="mt-2 text-sm text-muted">
              The error was contained. Reload to restore the project from the server.
            </p>
            <Button className="mt-4" onClick={() => window.location.reload()}>
              Reload
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function UnauthorizedListener() {
  const navigate = useNavigate();
  const client = useQueryClient();
  useEffect(() => {
    const handler = () => {
      client.clear();
      navigate(`/login?returnTo=${encodeURIComponent(window.location.pathname)}`, { replace: true });
    };
    window.addEventListener("bound:unauthorized", handler);
    return () => window.removeEventListener("bound:unauthorized", handler);
  }, [navigate, client]);
  return null;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <UnauthorizedListener />
        <ErrorBoundary>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <RequireSession>
                  <HomePage />
                </RequireSession>
              }
            />
            <Route
              path="/projects/:projectId"
              element={
                <RequireSession>
                  <ProjectLayout />
                </RequireSession>
              }
            >
              <Route index element={<StageRedirect />} />
              <Route path="intake" element={<IntakePage />} />
              <Route path="research" element={<ResearchPage />} />
              <Route path="outline" element={<OutlinePage />} />
              <Route path="plan" element={<PlanPage />} />
              <Route path="style" element={<StylePage />} />
              <Route path="design" element={<DesignPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
        <Toaster position="bottom-right" richColors closeButton />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
