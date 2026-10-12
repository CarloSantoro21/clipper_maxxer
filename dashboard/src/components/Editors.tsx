"use client";

import { CaptionStyle, Metrics, PLATFORMS, Platform, Task, fmtViews } from "@/lib/api";
import { Field, ProgressBar } from "./ui";

const PRESETS: { value: CaptionStyle["preset"]; label: string }[] = [
  { value: "karaoke", label: "Karaoke (resalta la palabra)" },
  { value: "pop", label: "Pop (resalta y agranda)" },
  { value: "plain", label: "Simple" },
];

const POSITIONS: { value: CaptionStyle["position"]; label: string }[] = [
  { value: "upper", label: "Arriba" },
  { value: "center", label: "Centro" },
  { value: "lower", label: "Abajo" },
];

const PLATFORM_LABEL: Record<Platform, string> = { tiktok: "TikTok", instagram: "Instagram", youtube: "YouTube", x: "X" };

export function CaptionEditor({ value, onChange }: { value: CaptionStyle; onChange: (v: CaptionStyle) => void }) {
  const set = <K extends keyof CaptionStyle>(k: K, v: CaptionStyle[K]) => onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Estilo">
        <select className="field" value={value.preset} onChange={(e) => set("preset", e.target.value as CaptionStyle["preset"])}>
          {PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Palabras por línea">
        <input
          type="number"
          min={1}
          max={8}
          className="field num"
          value={value.words_per_line}
          onChange={(e) => set("words_per_line", Math.max(1, Math.min(8, Number(e.target.value) || 1)))}
        />
      </Field>
      <fieldset className="sm:col-span-2">
        <legend className="mb-1 text-[13px] font-semibold text-ink">Posición</legend>
        <div className="grid grid-cols-3 gap-1.5">
          {POSITIONS.map((p) => (
            <button
              key={p.value}
              type="button"
              aria-pressed={value.position === p.value}
              onClick={() => set("position", p.value)}
              className={`btn ${value.position === p.value ? "btn-primary" : ""}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </fieldset>
      <ColorField label="Color del texto" value={value.color} onChange={(v) => set("color", v)} />
      <ColorField label="Color de la palabra activa" value={value.highlight} onChange={(v) => set("highlight", v)} />
      <label className="flex items-center gap-2 text-sm text-ink sm:col-span-2">
        <input type="checkbox" checked={value.uppercase} onChange={(e) => set("uppercase", e.target.checked)} className="size-4 accent-[var(--accent)]" />
        Todo en mayúsculas
      </label>
      <CaptionPreview style={value} />
    </div>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <Field label={label}>
      <div className="flex gap-2">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          className="h-[38px] w-12 shrink-0 cursor-pointer rounded-md border border-line bg-surface p-1"
          aria-label={`${label} (selector)`}
        />
        <input
          className="field num uppercase"
          value={value}
          maxLength={7}
          pattern="#[0-9A-Fa-f]{6}"
          onChange={(e) => onChange(e.target.value.toUpperCase())}
        />
      </div>
    </Field>
  );
}

/** Vista previa aproximada (el render real es libass; esto sólo orienta). */
function CaptionPreview({ style }: { style: CaptionStyle }) {
  const words = ["esto", "nadie", "te", "lo", "dice", "así"].slice(0, Math.min(style.words_per_line, 6));
  const active = Math.min(1, words.length - 1);
  return (
    <div className="sm:col-span-2">
      <p className="mb-1 text-[13px] font-semibold text-ink">Vista previa aproximada</p>
      <div className="flex h-28 rounded-md bg-frame px-4" style={{ alignItems: style.position === "upper" ? "flex-start" : style.position === "center" ? "center" : "flex-end" }}>
        <p
          className="w-full py-3 text-center text-[22px] font-black leading-tight"
          style={{ color: style.color, WebkitTextStroke: "1px #000", paintOrder: "stroke fill", textShadow: "0 2px 0 #000" }}
        >
          {words.map((w, i) => (
            <span
              key={i}
              style={
                i === active && style.preset !== "plain"
                  ? { color: style.highlight, display: "inline-block", transform: style.preset === "pop" ? "scale(1.12)" : undefined }
                  : undefined
              }
            >
              {style.uppercase ? w.toUpperCase() : w}
              {i < words.length - 1 ? " " : ""}
            </span>
          ))}
        </p>
      </div>
    </div>
  );
}

export function MetricsEditor({ value, onChange }: { value: Metrics; onChange: (v: Metrics) => void }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Link publicado" className="sm:col-span-2">
        <input
          className="field"
          type="url"
          placeholder="https://www.tiktok.com/@cuenta/video/…"
          value={value.published_url ?? ""}
          onChange={(e) => onChange({ ...value, published_url: e.target.value || null })}
        />
      </Field>
      <Field label="Plataforma">
        <select
          className="field"
          value={value.platform ?? ""}
          onChange={(e) => onChange({ ...value, platform: (e.target.value || null) as Platform | null })}
        >
          <option value="">Sin elegir</option>
          {PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {PLATFORM_LABEL[p]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Fecha de publicación">
        <input
          className="field num"
          type="date"
          value={value.published_at ?? ""}
          onChange={(e) => onChange({ ...value, published_at: e.target.value || null })}
        />
      </Field>
      <Field label="Vistas" hint={value.views != null ? `${fmtViews(value.views)} vistas` : undefined}>
        <input
          className="field num"
          type="number"
          min={0}
          inputMode="numeric"
          value={value.views ?? ""}
          onChange={(e) => onChange({ ...value, views: e.target.value === "" ? null : Math.max(0, Math.round(Number(e.target.value))) })}
        />
      </Field>
    </div>
  );
}

export function TaskStatus({ task }: { task: Task | null }) {
  if (!task) return null;
  const label =
    task.status === "queued"
      ? "En cola…"
      : task.status === "running"
        ? `${task.step}…`
        : task.status === "done"
          ? "Render listo"
          : `Falló: ${task.error}`;
  return (
    <div className="space-y-1.5" aria-live="polite">
      <div className="flex justify-between text-[13px]">
        <span className={task.status === "error" ? "text-st-rejected" : "text-ink"}>{label}</span>
        {task.status !== "error" && <span className="num text-mute">{Math.round(task.progress * 100)}%</span>}
      </div>
      {task.status !== "done" && <ProgressBar value={task.progress} error={task.status === "error"} />}
    </div>
  );
}

export function Section({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-[16px] font-bold text-ink">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function tagsToText(tags: string[]) {
  return tags.map((t) => `#${t}`).join(" ");
}

export function textToTags(text: string) {
  return text
    .split(/[\s,]+/)
    .map((t) => t.replace(/^#+/, "").trim())
    .filter(Boolean);
}
