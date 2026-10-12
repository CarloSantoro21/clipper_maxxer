"use client";

import { useState } from "react";
import { STATUS_LABEL, Status } from "@/lib/api";

export const TALLY: Record<Status, string> = {
  draft: "bg-st-draft",
  rendered: "bg-st-rendered",
  approved: "bg-st-approved",
  rejected: "bg-st-rejected",
  published: "bg-st-published",
};

export function StatusPill({ status }: { status: Status }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] font-medium text-ink">
      <span className={`size-2 rounded-full ${TALLY[status]}`} aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function CopyButton({ text, label = "Copiar", className = "" }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className={`btn ${className}`}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          // http en la red local: navigator.clipboard no existe; usamos el método viejo
          const ta = document.createElement("textarea");
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
        }
        setDone(true);
        setTimeout(() => setDone(false), 1400);
      }}
    >
      {done ? "Copiado" : label}
    </button>
  );
}

export function ErrorNote({ children }: { children: React.ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="rounded-md border border-st-rejected/40 bg-st-rejected/10 px-3 py-2 text-sm text-ink">
      {children}
    </p>
  );
}

export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-[13px] font-semibold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-mute">{hint}</span>}
    </label>
  );
}

export function ProgressBar({ value, error }: { value: number; error?: boolean }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-sunken" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${error ? "bg-st-rejected" : "bg-accent"}`}
        style={{ width: `${Math.max(4, value * 100)}%` }}
      />
    </div>
  );
}

export function PageHead({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <h1 className="text-[26px] font-bold leading-tight tracking-[-0.01em] text-ink">{title}</h1>
      {children}
    </div>
  );
}
