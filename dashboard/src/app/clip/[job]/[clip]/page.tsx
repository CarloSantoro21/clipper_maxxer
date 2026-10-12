"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CaptionEditor, MetricsEditor, Section, TaskStatus, tagsToText, textToTags } from "@/components/Editors";
import { CopyButton, ErrorNote, Field, StatusPill } from "@/components/ui";
import { Clip, Job, STATUSES, STATUS_LABEL, Status, Task, fmtDuration, fmtTime, mediaUrl, send } from "@/lib/api";
import { useApi, useTask } from "@/lib/hooks";

type Form = Pick<
  Clip,
  "hook" | "start" | "end" | "title" | "captions" | "crop_x" | "status" | "published_url" | "platform" | "views" | "published_at"
> & { hashtags: string };

function toForm(c: Clip): Form {
  return {
    hook: c.hook,
    start: c.start,
    end: c.end,
    title: c.title,
    hashtags: tagsToText(c.hashtags),
    captions: c.captions,
    crop_x: c.crop_x,
    status: c.status,
    published_url: c.published_url,
    platform: c.platform,
    views: c.views,
    published_at: c.published_at,
  };
}

function toPatch(f: Form) {
  return { ...f, hashtags: textToTags(f.hashtags) };
}

const round = (n: number) => Math.round(n * 1000) / 1000;

export default function ClipPage() {
  const params = useParams<{ job: string; clip: string }>();
  const jobId = decodeURIComponent(params.job);
  const clipId = decodeURIComponent(params.clip);
  const job = useApi<Job>(`/api/jobs/${encodeURIComponent(jobId)}`);
  const clip = job.data?.clips.find((c) => c.id === clipId) ?? null;

  const [form, setForm] = useState<Form | null>(null);
  const [baseline, setBaseline] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { task, track } = useTask(() => job.reload());
  const loadedFor = useRef<string | null>(null);

  // Cuando llegan datos nuevos del servidor (primera carga, render terminado o cambio hecho por el chat),
  // reemplazamos el formulario sólo si no hay cambios sin guardar.
  const serverKey = clip ? JSON.stringify(toForm(clip)) : "";
  useEffect(() => {
    if (!clip) return;
    const dirty = form !== null && JSON.stringify(form) !== baseline;
    if (loadedFor.current !== clipId || !dirty) {
      loadedFor.current = clipId;
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm(toForm(clip));
      setBaseline(serverKey);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverKey, clipId]);

  const dirty = form !== null && JSON.stringify(form) !== baseline;
  const rendering = task?.status === "queued" || task?.status === "running";

  async function save(render: boolean) {
    if (!form) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await send<Clip>("PATCH", `/api/jobs/${jobId}/clips/${clipId}`, toPatch(form));
      job.setData((j) => (j ? { ...j, clips: j.clips.map((c) => (c.id === clipId ? updated : c)) } : j));
      const f = toForm(updated);
      setForm(f);
      setBaseline(JSON.stringify(f));
      if (render) track(await send<Task>("POST", `/api/jobs/${jobId}/clips/${clipId}/render`));
      else setNotice("Guardado");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (job.error && !job.data) return <ErrorNote>{job.error}</ErrorNote>;
  if (!form || !clip) {
    return job.data ? <ErrorNote>No existe el clip {clipId} en {jobId}.</ErrorNote> : <p className="text-mute">Cargando…</p>;
  }

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm({ ...form, [k]: v });
  const nudge = (k: "start" | "end", d: number) => set(k, round(Math.max(0, form[k] + d)));
  const duration = form.end - form.start;
  const video = mediaUrl(clip.video_url);
  const index = job.data!.clips.findIndex((c) => c.id === clipId);
  const prev = job.data!.clips[index - 1];
  const next = job.data!.clips[index + 1];

  return (
    <div className="mx-auto max-w-[1200px]">
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
        <Link href="/" className="text-mute hover:text-ink">
          Revisión
        </Link>
        <span className="text-line">/</span>
        <span className="text-mute">{job.data!.title || jobId}</span>
        <span className="ml-auto flex gap-1.5">
          {prev && (
            <Link className="btn px-2.5 py-1 text-[13px]" href={`/clip/${encodeURIComponent(jobId)}/${prev.id}`}>
              Anterior: {prev.id}
            </Link>
          )}
          {next && (
            <Link className="btn px-2.5 py-1 text-[13px]" href={`/clip/${encodeURIComponent(jobId)}/${next.id}`}>
              Siguiente: {next.id}
            </Link>
          )}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(280px,400px)_1fr]">
        <div className="space-y-3 lg:sticky lg:top-20 lg:self-start">
          <div className="overflow-hidden rounded-lg bg-frame">
            {video ? (
              <video key={clip.video_url} src={video} controls playsInline preload="metadata" className="mx-auto aspect-[9/16] max-h-[78dvh] w-full object-contain" />
            ) : (
              <div className="grid aspect-[9/16] place-items-center text-sm text-white/60">Sin render todavía</div>
            )}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-[13px] text-mute">
            <StatusPill status={clip.status} />
            <span className="num">
              {clip.id} · score <b className="text-ink">{clip.score.toFixed(1)}</b> · {clip.account || "sin cuenta"}
            </span>
          </div>
          {clip.why && <p className="text-sm text-mute">{clip.why}</p>}
          {clip.issues.length > 0 && (
            <ul className="space-y-1 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-[13px] text-ink">
              {clip.issues.map((i) => (
                <li key={i}>⚠ {i}</li>
              ))}
            </ul>
          )}
        </div>

        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            save(true);
          }}
        >
          <h1 className="text-[24px] font-bold leading-tight text-ink">{form.hook || "Sin hook"}</h1>

          <Section title="Corte">
            <div className="space-y-4">
              <Field label="Hook (texto en pantalla los primeros segundos)" hint={`${form.hook.trim().split(/\s+/).filter(Boolean).length} palabras; ideal 8 o menos`}>
                <input className="field text-[16px] font-semibold" value={form.hook} onChange={(e) => set("hook", e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <TimeField label="Inicio" value={form.start} onChange={(v) => set("start", v)} onNudge={(d) => nudge("start", d)} />
                <TimeField label="Fin" value={form.end} onChange={(v) => set("end", v)} onNudge={(d) => nudge("end", d)} />
              </div>
              <p className={`num text-sm ${duration <= 0 ? "text-st-rejected" : "text-mute"}`}>
                Duración: <b className="text-ink">{duration > 0 ? fmtDuration(duration) : "el fin debe ir después del inicio"}</b>
                {job.data!.source_duration ? <> · fuente de {fmtTime(job.data!.source_duration)}</> : null}
              </p>
              <Field label="Encuadre horizontal" hint="Dónde cae el recorte 9:16 sobre el video original.">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-mute">Izq.</span>
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={form.crop_x}
                    onChange={(e) => set("crop_x", Number(e.target.value))}
                    className="flex-1 accent-[var(--accent)]"
                  />
                  <span className="text-xs text-mute">Der.</span>
                  <span className="num w-10 text-right text-sm text-ink">{form.crop_x.toFixed(2)}</span>
                </div>
              </Field>
            </div>
          </Section>

          <Section title="Caption para publicar" aside={<CopyButton text={`${form.title}\n\n${form.hashtags}`.trim()} label="Copiar caption" className="text-[13px]" />}>
            <div className="space-y-4">
              <Field label="Descripción">
                <textarea className="field min-h-[84px]" value={form.title} onChange={(e) => set("title", e.target.value)} />
              </Field>
              <Field label="Hashtags" hint="Separados por espacio. Los obligatorios de la campaña se agregan solos al planear.">
                <input className="field" value={form.hashtags} onChange={(e) => set("hashtags", e.target.value)} />
              </Field>
            </div>
          </Section>

          <Section title="Subtítulos">
            <CaptionEditor value={form.captions} onChange={(v) => set("captions", v)} />
          </Section>

          <Section title="Estado y métricas">
            <div className="space-y-4">
              <fieldset>
                <legend className="mb-1 text-[13px] font-semibold text-ink">Estado</legend>
                <div className="flex flex-wrap gap-1.5">
                  {STATUSES.map((s: Status) => (
                    <button
                      key={s}
                      type="button"
                      aria-pressed={form.status === s}
                      onClick={() => set("status", s)}
                      className={`btn text-[13px] ${form.status === s ? "btn-primary" : ""}`}
                    >
                      {STATUS_LABEL[s]}
                    </button>
                  ))}
                </div>
              </fieldset>
              <MetricsEditor value={form} onChange={(m) => setForm({ ...form, ...m })} />
            </div>
          </Section>

          <div className="sticky bottom-16 z-10 -mx-1 space-y-2 rounded-lg border border-line bg-surface/95 p-3 backdrop-blur sm:bottom-3">
            <ErrorNote>{error}</ErrorNote>
            <TaskStatus task={task} />
            <div className="flex flex-wrap items-center gap-2">
              <button type="submit" className="btn btn-primary" disabled={saving || rendering || duration <= 0 || form.status === "rejected"}>
                {saving ? "Guardando…" : rendering ? "Renderizando…" : "Guardar y re-renderizar"}
              </button>
              <button type="button" className="btn" disabled={saving || !dirty} onClick={() => save(false)}>
                Sólo guardar
              </button>
              <button type="button" className="btn" disabled={!dirty} onClick={() => setForm(toForm(clip))}>
                Descartar cambios
              </button>
              <span className="text-[13px] text-mute" aria-live="polite">
                {dirty ? "Cambios sin guardar" : notice}
              </span>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function TimeField({
  label,
  value,
  onChange,
  onNudge,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  onNudge: (d: number) => void;
}) {
  return (
    <Field label={`${label} (s)`} hint={fmtTime(value)}>
      <div className="flex gap-1.5">
        <button type="button" className="btn num px-2.5" onClick={() => onNudge(-0.5)} aria-label={`${label} menos 0.5 segundos`}>
          −0.5
        </button>
        <input
          type="number"
          step={0.1}
          min={0}
          className="field num text-center"
          value={value}
          onChange={(e) => onChange(round(Number(e.target.value)))}
        />
        <button type="button" className="btn num px-2.5" onClick={() => onNudge(0.5)} aria-label={`${label} más 0.5 segundos`}>
          +0.5
        </button>
      </div>
    </Field>
  );
}
