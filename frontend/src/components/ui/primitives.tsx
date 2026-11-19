import * as React from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, tone = "neutral", children, ...props }: React.HTMLAttributes<HTMLSpanElement> & { tone?: "neutral" | "brand" | "ok" | "warn" | "danger" }) {
  const tones: Record<string, string> = {
    neutral: "bg-surface-2 text-muted border-line",
    brand: "bg-brand-soft text-brand-strong border-indigo-200",
    ok: "bg-ok-soft text-ok border-green-200",
    warn: "bg-warn-soft text-warn border-amber-200",
    danger: "bg-danger-soft text-danger border-red-200",
  };
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}
      {...props}
    >
      {children}
    </span>
  );
}

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("app-card", className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-5 pb-3", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold text-ink", className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("text-sm text-muted", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5 pt-2", className)} {...props} />;
}
