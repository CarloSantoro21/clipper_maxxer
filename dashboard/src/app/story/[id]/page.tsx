"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CaptionEditor, MetricsEditor, Section, TaskStatus, tagsToText, textToTags } from "@/components/Editors";
import { CopyButton, ErrorNote, Field, StatusPill } from "@/components/ui";
import { STATUSES, STATUS_LABEL, Story, Task, mediaUrl, send } from "@/lib/api";
import { useApi, useTask } from "@/lib/hooks";

type Form = Pick<
  Story,
  "title" | "hook" | "script" | "rate" | "part" | "captions" | "status" | "published_url" | "platform" | "views" | "published_at"
> & { hashtags: string };

const toForm = (s: Story): Form => ({
  title: s.title,
  hook: s.hook,
  script: s.script,
  rate: s.rate,
  part: s.part,
  captions: s.captions,
  status: s.status,
  hashtags: tagsToText(s.hashtags),
  published_url: s.published_url,
  platform: s.platform,
  views: s.views,
  published_at: s.published_at,
});

export default function StoryPage() {
  const { id: raw } = useParams<{ id: string }>();
  const id = decodeURIComponent(raw);
  const story = useApi<Story>(`/api/stories/${encodeURIComponent(id)}`);
  const [form, setForm] = useState<Form | null>(null);
  const [baseline, setBaseline] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { task, track } = useTask(() => story.reload());
  const loadedFor = useRef<string | null>(null);

  const serverKey = story.data ? JSON.stringify(toForm(story.data)) : "";
  useEffect(() => {
    if (!story.data) return;
    const dirty = form !== null && JSON.stringify(form) !== baseline;
    if (loadedFor.current !== id || !dirty) {
      loadedFor.current = id;
       
      setForm(toForm(story.data));
      setBaseline(serverKey);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverKey, id]);

  if (story.error && !story.data) return <ErrorNote>{story.error}</ErrorNote>;
  if (!form || !story.data) return <p className="text-mute">Cargando…</p>;
  const s = story.data;
  const dirty = JSON.stringify(form) !== baseline;
  const rendering = task?.status === "queued" || task?.status === "running";
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm({ ...form, [k]: v });
  const words = form.script.trim().split(/\s+/).filter(Boolean).length;

  async function save(render: boolean) {
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await send<Story>("PATCH", `/api/stories/${id}`, { ...form, hashtags: textToTags(form.hashtags) });
      story.setData(updated);
      const f = toForm(updated);
      setForm(f);
      setBaseline(JSON.stringify(f));
      if (render) track(await send<Task>("POST", `/api/stories/${id}/render`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1200px]">
      <div className="mb-4 flex items-center gap-3 text-sm">
        <Link href="/" className="text-mute hover:text-ink">
          Revisión
        </Link>
        <span className="text-line">/</span>
        <span className="text-mute">Story {s.id}</span>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(280px,400px)_1fr]">
        <div className="space-y-3 lg:sticky lg:top-20 lg:self-start">
          <div className="overflow-hidden rounded-lg bg-frame">
            {s.video_url ? (
              <video key={s.video_url} src={mediaUrl(s.video_url)!} controls playsInline preload="metadata" className="aspect-[9/16] max-h-[78dvh] w-full object-contain" />
            ) : (
              <div className="grid aspect-[9/16] place-items-center text-sm text-white/60">Sin render todavía</div>
            )}
          </div>
          <div className="flex items-center justify-between text-[13px] text-mute">
            <StatusPill status={s.status} />
            <span>
              {s.account}
              {s.part ? `, parte ${s.part}` : ""}
            </span>
          </div>
          <p className="rounded-md border border-line bg-surface px-3 py-2 text-[13px] text-mute">
            Si la voz suena realista, activa la etiqueta de contenido generado con IA al publicar.
          </p>
        </div>

        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            save(true);
          }}
        >
          <h1 className="text-[24px] font-bold leading-tight text-ink">{form.title}</h1>
          <Section title="Guion">
            <div className="space-y-4">
              <Field label="Título">
                <input className="field" value={form.title} onChange={(e) => set("title", e.target.value)} />
              </Field>
              <Field label="Hook (primera frase)">
                <input className="field font-semibold" value={form.hook} onChange={(e) => set("hook", e.target.value)} />
              </Field>
              <Field label="Texto narrado" hint={`${words} palabras, unos ${Math.round(words / 2.6)} s de voz`}>
                <textarea className="field min-h-[220px] leading-relaxed" value={form.script} onChange={(e) => set("script", e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Velocidad de la voz" hint="Formato edge-tts, ej. +8% o -5%">
                  <input className="field num" value={form.rate} onChange={(e) => set("rate", e.target.value)} />
                </Field>
                <Field label="Parte">
                  <input
                    className="field num"
                    type="number"
                    min={1}
                    value={form.part ?? ""}
                    onChange={(e) => set("part", e.target.value ? Number(e.target.value) : null)}
                  />
                </Field>
              </div>
            </div>
          </Section>
          <Section title="Caption para publicar" aside={<CopyButton text={`${form.title}\n\n${form.hashtags}`} label="Copiar caption" className="text-[13px]" />}>
            <Field label="Hashtags">
              <input className="field" value={form.hashtags} onChange={(e) => set("hashtags", e.target.value)} />
            </Field>
          </Section>
          <Section title="Subtítulos">
            <CaptionEditor value={form.captions} onChange={(v) => set("captions", v)} />
          </Section>
          <Section title="Estado y métricas">
            <div className="space-y-4">
              <div className="flex flex-wrap gap-1.5">
                {STATUSES.map((st) => (
                  <button key={st} type="button" aria-pressed={form.status === st} onClick={() => set("status", st)} className={`btn text-[13px] ${form.status === st ? "btn-primary" : ""}`}>
                    {STATUS_LABEL[st]}
                  </button>
                ))}
              </div>
              <MetricsEditor value={form} onChange={(m) => setForm({ ...form, ...m })} />
            </div>
          </Section>
          <div className="sticky bottom-16 z-10 space-y-2 rounded-lg border border-line bg-surface/95 p-3 backdrop-blur sm:bottom-3">
            <ErrorNote>{error}</ErrorNote>
            <TaskStatus task={task} />
            <div className="flex flex-wrap items-center gap-2">
              <button type="submit" className="btn btn-primary" disabled={saving || rendering}>
                {saving ? "Guardando…" : rendering ? "Renderizando…" : "Guardar y re-renderizar"}
              </button>
              <button type="button" className="btn" disabled={saving || !dirty} onClick={() => save(false)}>
                Sólo guardar
              </button>
              {dirty && <span className="text-[13px] text-mute">Cambios sin guardar</span>}
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
