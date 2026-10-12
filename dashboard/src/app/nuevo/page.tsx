"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Section } from "@/components/Editors";
import { ErrorNote, Field, PageHead, ProgressBar } from "@/components/ui";
import { ApiError, Campaign, Task, send } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const TASK_LABEL: Record<Task["status"], string> = {
  queued: "En cola",
  running: "Corriendo",
  done: "Listo",
  error: "Falló",
};

function resultLink(t: Task) {
  if (t.result.story) return { href: `/story/${encodeURIComponent(t.result.story)}`, label: "Ver story" };
  if (t.result.job && t.result.clip)
    return { href: `/clip/${encodeURIComponent(t.result.job)}/${encodeURIComponent(t.result.clip)}`, label: "Ver clip" };
  if (t.result.job) return { href: "/", label: "Ver clips en Revisión" };
  return null;
}

function TaskRow({ t }: { t: Task }) {
  const [open, setOpen] = useState(t.status === "error");
  const link = t.status === "done" ? resultLink(t) : null;
  return (
    <li className="border-b border-line py-3 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{t.label}</p>
          <p className={`text-[13px] ${t.status === "error" ? "text-st-rejected" : "text-mute"}`}>
            {TASK_LABEL[t.status]}
            {t.status === "running" && t.step ? ` · ${t.step}` : ""}
            {t.status === "error" && t.error ? ` · ${t.error}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {link && (
            <Link href={link.href} className="btn text-[13px]">
              {link.label}
            </Link>
          )}
          {t.log.length > 0 && (
            <button type="button" className="btn text-[13px]" aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? "Ocultar log" : "Log"}
            </button>
          )}
        </div>
      </div>
      {(t.status === "running" || t.status === "queued") && (
        <div className="mt-2">
          <ProgressBar value={t.progress} />
        </div>
      )}
      {open && (
        <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-sunken p-2 text-xs leading-relaxed text-ink">
          {t.log.join("\n")}
        </pre>
      )}
    </li>
  );
}

function ClipForm({ campaigns, onQueued }: { campaigns: Campaign[]; onQueued: () => void }) {
  const active = campaigns.filter((c) => c.active);
  const [src, setSrc] = useState("");
  const [campaign, setCampaign] = useState("");
  const [n, setN] = useState(5);
  const [permission, setPermission] = useState("");
  const [needPermission, setNeedPermission] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const selected = active.find((c) => c.slug === campaign);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!src.trim()) return setError("Pega el link del video.");
    if (needPermission && !permission.trim()) return setError("Escribe de dónde viene el permiso para usar este video.");
    setBusy(true);
    setError(null);
    try {
      await send("POST", "/api/jobs", {
        src: src.trim(),
        campaign: campaign || null,
        n,
        permission_note: permission.trim() || null,
      });
      setSrc("");
      setPermission("");
      setNeedPermission(false);
      onQueued();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setNeedPermission(true);
        setError(err.message);
      } else setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <Field label="Link del video" hint="YouTube, Drive o un archivo local. Debe ser material autorizado por la campaña.">
        <input
          className="field"
          type="text"
          inputMode="url"
          placeholder="https://youtu.be/…"
          value={src}
          onChange={(e) => {
            setSrc(e.target.value);
            setError(null);
          }}
        />
      </Field>
      {selected && selected.source_urls.length > 0 && (
        <div className="text-[13px] text-mute">
          Material de esta campaña:{" "}
          {selected.source_urls.map((u) => (
            <button key={u} type="button" className="mr-2 underline decoration-line underline-offset-2 hover:text-ink" onClick={() => setSrc(u)}>
              {u.length > 42 ? `${u.slice(0, 42)}…` : u}
            </button>
          ))}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-[1fr_120px]">
        <Field label="Campaña">
          <select className="field" value={campaign} onChange={(e) => setCampaign(e.target.value)}>
            <option value="">Sin campaña (contenido propio o libre)</option>
            {active.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name} · ${c.rate_per_1k}/1K
              </option>
            ))}
          </select>
        </Field>
        <Field label="Clips">
          <input className="field num" type="number" min={1} max={20} value={n} onChange={(e) => setN(Math.min(20, Math.max(1, Number(e.target.value) || 1)))} />
        </Field>
      </div>
      {(needPermission || !campaign) && (
        <Field label="¿De dónde viene el permiso?" hint="Obligatorio si el link no está en una campaña activa: contenido propio, licencia libre, programa de clipping del creador…">
          <input className="field" type="text" value={permission} onChange={(e) => setPermission(e.target.value)} />
        </Field>
      )}
      <ErrorNote>{error}</ErrorNote>
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? "Enviando…" : "Crear clips"}
      </button>
    </form>
  );
}

function StoryForm({ onQueued }: { onQueued: () => void }) {
  const [premise, setPremise] = useState("");
  const [seconds, setSeconds] = useState(75);
  const [part, setPart] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (premise.trim().length < 3) return setError("Escribe la premisa de la historia.");
    setBusy(true);
    setError(null);
    try {
      await send("POST", "/api/stories", { premise: premise.trim(), seconds, part: part ? Number(part) : null, render: true });
      setPremise("");
      onQueued();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <Field label="Premisa" hint="Ej.: Mi esposa me engañó con mi mejor amigo y la perdoné, pero no por lo que crees.">
        <textarea
          className="field min-h-24"
          value={premise}
          onChange={(e) => {
            setPremise(e.target.value);
            setError(null);
          }}
        />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Duración (s)" hint="60–90 s rinde mejor; >60 s cuenta para Creator Rewards">
          <input className="field num" type="number" min={15} max={180} value={seconds} onChange={(e) => setSeconds(Math.min(180, Math.max(15, Number(e.target.value) || 75)))} />
        </Field>
        <Field label="Parte" hint="Vacío si es historia única">
          <input className="field num" type="number" min={1} max={20} value={part} onChange={(e) => setPart(e.target.value)} />
        </Field>
      </div>
      <ErrorNote>{error}</ErrorNote>
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? "Enviando…" : "Escribir y renderizar"}
      </button>
    </form>
  );
}

export default function NuevoPage() {
  const campaigns = useApi<Campaign[]>("/api/campaigns");
  const tasks = useApi<Task[]>("/api/tasks");
  const { reload } = tasks;
  const running = (tasks.data || []).some((t) => t.status === "queued" || t.status === "running");

  // mientras haya tareas vivas, refrescamos cada 1.5 s
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(reload, 1500);
    return () => clearInterval(timer);
  }, [running, reload]);

  const list = [...(tasks.data || [])].sort((a, b) => b.created_at - a.created_at);

  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title="Nuevo" />
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Clips de una campaña">
          <ClipForm campaigns={campaigns.data || []} onQueued={reload} />
        </Section>
        <Section title="Story sobre gameplay">
          <StoryForm onQueued={reload} />
        </Section>
      </div>
      <div className="mt-5">
        <Section title="Tareas" aside={<button type="button" className="btn text-[13px]" onClick={reload}>Actualizar</button>}>
          {tasks.error && <ErrorNote>{tasks.error}</ErrorNote>}
          {list.length === 0 ? (
            <p className="text-sm text-mute">No hay tareas. Las que lances aquí aparecen con su progreso y su log.</p>
          ) : (
            <ul>
              {list.map((t) => (
                <TaskRow key={t.id} t={t} />
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}
