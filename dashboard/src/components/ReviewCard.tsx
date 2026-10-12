"use client";

import Link from "next/link";
import { useState } from "react";
import { Clip, Status, Story, fmtDuration, fmtViews, mediaUrl, send } from "@/lib/api";
import { CopyButton, StatusPill, TALLY } from "./ui";

export type Item = Clip | Story;

export function itemHref(it: Item) {
  return it.kind === "clip" ? `/clip/${encodeURIComponent(it.job_id)}/${encodeURIComponent(it.id)}` : `/story/${encodeURIComponent(it.id)}`;
}

export function itemPatchPath(it: Item) {
  return it.kind === "clip" ? `/api/jobs/${it.job_id}/clips/${it.id}` : `/api/stories/${it.id}`;
}

const ACTIONS: { status: Status; label: string }[] = [
  { status: "approved", label: "Aprobar" },
  { status: "rejected", label: "Rechazar" },
  { status: "published", label: "Publicado" },
];

export default function ReviewCard({ item, onChange }: { item: Item; onChange: (it: Item) => void }) {
  const [busy, setBusy] = useState<Status | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const video = mediaUrl(item.video_url);
  const duration = item.kind === "clip" ? item.duration : null;

  async function setStatus(status: Status) {
    // volver a pulsar el estado activo lo regresa a "renderizado"
    const next: Status = item.status === status ? (item.video_url ? "rendered" : "draft") : status;
    setBusy(status);
    setErr(null);
    try {
      onChange(await send<Item>("PATCH", itemPatchPath(item), { status: next }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <article className="flex flex-col overflow-hidden rounded-lg border border-line bg-surface">
      <div className={`h-1 ${TALLY[item.status]}`} aria-hidden />
      <div className="relative bg-frame">
        {video ? (
          <video
            src={video}
            poster={mediaUrl(item.thumb_url) ?? undefined}
            controls
            playsInline
            preload="metadata"
            className="aspect-[9/16] w-full object-contain"
          />
        ) : (
          <div className="grid aspect-[9/16] w-full place-items-center px-6 text-center text-sm text-white/60">
            Sin render todavía
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2.5 p-3">
        <div className="flex items-center justify-between gap-2 text-[13px] text-mute">
          <StatusPill status={item.status} />
          <span className="num">
            {item.kind === "clip" ? (
              <>
                {duration != null && fmtDuration(duration)} · score <b className="font-semibold text-ink">{item.score.toFixed(1)}</b>
              </>
            ) : (
              <>Story{item.part ? `, parte ${item.part}` : ""}</>
            )}
          </span>
        </div>

        <Link href={itemHref(item)} className="text-[16px] font-bold leading-snug text-ink hover:text-accent">
          {item.hook || item.title}
        </Link>

        {item.kind === "clip" && item.why && <p className="text-[13px] leading-snug text-mute">{item.why}</p>}

        <p className="text-xs text-mute">
          {item.kind === "clip" ? (
            <>
              <span className="text-ink">{item.account || "sin cuenta"}</span>
              {item.campaign ? `, campaña ${item.campaign}` : ""} · {item.job_id}/{item.id}
            </>
          ) : (
            <>
              <span className="text-ink">{item.account}</span> · {item.id}
            </>
          )}
          {item.views != null && <> · {fmtViews(item.views)} vistas</>}
        </p>

        {item.kind === "clip" && item.issues.length > 0 && (
          <ul className="space-y-1 rounded-md border border-warn/40 bg-warn/10 px-2.5 py-1.5 text-xs text-ink">
            {item.issues.map((i) => (
              <li key={i}>⚠ {i}</li>
            ))}
          </ul>
        )}

        <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
          {ACTIONS.map((a) => {
            const active = item.status === a.status;
            return (
              <button
                key={a.status}
                type="button"
                aria-pressed={active}
                disabled={busy !== null}
                onClick={() => setStatus(a.status)}
                className={`btn flex-1 px-2 text-[13px] ${active ? "border-transparent text-white " + TALLY[a.status] : ""}`}
              >
                {busy === a.status ? "…" : a.label}
              </button>
            );
          })}
        </div>
        <div className="flex gap-1.5">
          <CopyButton text={item.caption} label="Copiar caption" className="flex-1 text-[13px]" />
          <Link href={itemHref(item)} className="btn flex-1 text-[13px]">
            Ajustar
          </Link>
        </div>
        {err && <p className="text-xs text-st-rejected">{err}</p>}
      </div>
    </article>
  );
}
