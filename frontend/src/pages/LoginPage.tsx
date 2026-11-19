import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { qk } from "@/api/keys";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/dialog";
import { useAuth } from "@/hooks/useProjectData";
import { errorText } from "@/lib/messages";

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("pilot@boundppt.local");
  const [password, setPassword] = useState("boundppt-demo");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (auth.data) {
    return <Navigate to={params.get("returnTo") || "/"} replace />;
  }

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-brand text-lg font-black text-white">B</span>
          <div>
            <p className="text-lg font-bold tracking-tight text-ink">Bound PPT</p>
            <p className="text-sm text-muted">Expert-team PPT Agent · pilot</p>
          </div>
        </div>
        <form
          className="app-card p-6"
          onSubmit={async (event) => {
            event.preventDefault();
            setError("");
            setBusy(true);
            try {
              await api("/api/auth/login", { method: "POST", body: { email, password } });
              await queryClient.invalidateQueries({ queryKey: qk.auth });
              navigate(params.get("returnTo") || "/", { replace: true });
            } catch (err) {
              setError(errorText(err));
            } finally {
              setBusy(false);
            }
          }}
        >
          <h1 className="text-xl font-bold text-ink">Sign in to the pilot</h1>
          <p className="mt-1 text-sm text-muted">
            Accounts are provisioned by the pilot team. The demo credentials are prefilled locally.
          </p>
          <div className="mt-5 space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error ? (
              <p role="alert" className="rounded-xl border border-red-200 bg-danger-soft px-3 py-2 text-sm text-danger">
                {error}
              </p>
            ) : null}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </div>
        </form>
        <p className="mt-4 text-center text-xs text-muted">
          Materials are used only for your deck. No training on customer content by default.
        </p>
      </div>
    </div>
  );
}
