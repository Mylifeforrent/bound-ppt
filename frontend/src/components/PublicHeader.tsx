import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/primitives";

export function PublicHeader() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  return (
    <header className="border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2 font-bold tracking-tight text-ink">
          <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand text-sm font-black text-white">B</span>
          <span>Bound PPT</span>
        </Link>
        <div className="flex items-center gap-2">
          <Badge tone="neutral" className="hidden sm:inline-flex">
            Pilot
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Sign out"
            onClick={async () => {
              try {
                await api("/api/auth/logout", { method: "POST" });
              } finally {
                queryClient.clear();
                navigate("/login", { replace: true });
              }
            }}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
