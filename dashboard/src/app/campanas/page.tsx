"use client";

import { useState } from "react";
import { Section } from "@/components/Editors";
import { ErrorNote, Field, PageHead } from "@/components/ui";
import { Campaign, PLATFORMS, Platform, send } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const EMPTY: Campaign = {
  slug: "",
  name: "",
  url: "",
  niche: "",
  account: "",
  rate_per_1k: 0,
  platforms: ["tiktok", "instagram", "youtube"],
  min_seconds: 15,
  max_seconds: 90,
  language: "es",
  source_urls: [],
  required_hashtags: [],
  required_mentions: [],
  required_text: [],
  banned: [],
  notes: "",
  active: true,
};

const PLATFORM_LABEL: Record<Platform, string> = { tiktok: "TikTok", instagram: "Instagram", youtube: "YouTube", x: "X" };

const lines = (v: string[]) => v.join("\n");
const fromLines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

function slugify(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}

function ListField({ label, hint, value, onChange }: { label: string; hint?: string; value: string[]; onChange: (v: string[]) => void }) {
  // texto local para no comerse los saltos de línea mientras escribes
  const [text, setText] = useState(lines(value));
  return (
    <Field label={label} hint={hint ?? "Uno por línea"}>
      <textarea
        className="field min-h-20 text-[13px]"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          onChange(fromLines(e.target.value));
        }}
      />
    </Field>
  );
}

function CampaignEditor({
  initial,
  isNew,
  overwrite,
  onSaved,
  onCancel,
}: {
  initial: Campaign;
  isNew: boolean;
  overwrite?: boolean;
  onSaved: (c: Campaign) => void;
  onCancel: () => void;
}) {
  const [c, setC] = useState<Campaign>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Campaign>(k: K, v: Campaign[K]) => setC({ ...c, [k]: v });

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!c.name.trim()) return setError("Ponle nombre a la campaña.");
    if (!/^[a-z0-9][a-z0-9-]*$/.test(c.slug)) return setError("El slug sólo puede tener minúsculas, números y guiones.");
    if (c.max_seconds < c.min_seconds) return setError("La duración máxima es menor que la mínima.");
    if (c.platforms.length === 0) return setError("Elige al menos una plataforma.");
    setBusy(true);
    setError(null);
    try {
      const saved = await send<Campaign>("PUT", `/api/campaigns/${encodeURIComponent(c.slug)}`, c);
      onSaved(saved);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-4" noValidate>
      {overwrite && <ErrorNote>Ya existe una campaña con el slug “{c.slug}”. Si guardas, la reemplazas; cambia el slug si es otra.</ErrorNote>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nombre">
          <input
            className="field"
            value={c.name}
            onChange={(e) => setC({ ...c, name: e.target.value, slug: isNew && (!c.slug || c.slug === slugify(c.name)) ? slugify(e.target.value) : c.slug })}
          />
        </Field>
        <Field label="Slug" hint={isNew ? "Se usa en /clip y en el nombre del archivo" : "No se puede cambiar"}>
          <input className="field font-mono text-[13px]" value={c.slug} readOnly={!isNew} onChange={(e) => set("slug", slugify(e.target.value))} />
        </Field>
        <Field label="Link de la campaña">
          <input className="field" inputMode="url" value={c.url} onChange={(e) => set("url", e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Nicho">
            <input className="field" value={c.niche} onChange={(e) => set("niche", e.target.value)} />
          </Field>
          <Field label="Cuenta">
            <input className="field" placeholder="tech-es" value={c.account} onChange={(e) => set("account", e.target.value)} />
          </Field>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Field label="USD por 1K vistas">
          <input className="field num" type="number" step="0.1" min={0} value={c.rate_per_1k} onChange={(e) => set("rate_per_1k", Math.max(0, Number(e.target.value) || 0))} />
        </Field>
        <Field label="Mín. (s)">
          <input className="field num" type="number" min={1} value={c.min_seconds} onChange={(e) => set("min_seconds", Math.max(1, Number(e.target.value) || 1))} />
        </Field>
        <Field label="Máx. (s)">
          <input className="field num" type="number" min={1} value={c.max_seconds} onChange={(e) => set("max_seconds", Math.max(1, Number(e.target.value) || 1))} />
        </Field>
        <Field label="Idioma">
          <input className="field" value={c.language} onChange={(e) => set("language", e.target.value)} />
        </Field>
      </div>

      <fieldset>
        <legend className="mb-1 text-[13px] font-semibold text-ink">Plataformas</legend>
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((p) => {
            const on = c.platforms.includes(p);
            return (
              <button
                key={p}
                type="button"
                aria-pressed={on}
                className={`btn text-[13px] ${on ? "btn-primary" : ""}`}
                onClick={() => set("platforms", on ? c.platforms.filter((x) => x !== p) : [...c.platforms, p])}
              >
                {PLATFORM_LABEL[p]}
              </button>
            );
          })}
        </div>
      </fieldset>

      <ListField label="Material autorizado (links)" value={c.source_urls} onChange={(v) => set("source_urls", v)} />
      <div className="grid gap-4 sm:grid-cols-3">
        <ListField label="Hashtags obligatorios" hint="Sin #, uno por línea" value={c.required_hashtags} onChange={(v) => set("required_hashtags", v.map((t) => t.replace(/^#+/, "")))} />
        <ListField label="Menciones obligatorias" hint="Ej. @creador" value={c.required_mentions} onChange={(v) => set("required_mentions", v)} />
        <ListField label="Textos obligatorios" value={c.required_text} onChange={(v) => set("required_text", v)} />
      </div>
      <ListField label="Temas o palabras prohibidas" value={c.banned} onChange={(v) => set("banned", v)} />
      <Field label="Notas del brief">
        <textarea className="field min-h-20 text-[13px]" value={c.notes} onChange={(e) => set("notes", e.target.value)} />
      </Field>
      <label className="flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={c.active} onChange={(e) => set("active", e.target.checked)} />
        Campaña activa
      </label>

      <ErrorNote>{error}</ErrorNote>
      <div className="flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? "Guardando…" : "Guardar"}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </form>
  );
}

function ExtractBox({ onDraft }: { onDraft: (c: Campaign, exists: boolean) => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const extract = async () => {
    if (text.trim().length < 10) return setError("Pega el texto completo del brief.");
    setBusy(true);
    setError(null);
    try {
      const r = await send<{ draft: Campaign; exists: boolean }>("POST", "/api/campaigns/extract", { text });
      onDraft(r.draft, r.exists);
      setText("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <Field label="Texto del brief" hint="Copia el brief completo de Whop (reglas, tarifa, links). Claude arma un borrador que revisas antes de guardar.">
        <textarea
          className="field min-h-32 text-[13px]"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setError(null);
          }}
        />
      </Field>
      <ErrorNote>{error}</ErrorNote>
      <button type="button" className="btn btn-primary" disabled={busy} onClick={extract}>
        {busy ? "Claude está leyendo el brief…" : "Extraer con Claude"}
      </button>
    </div>
  );
}

export default function CampanasPage() {
  const campaigns = useApi<Campaign[]>("/api/campaigns");
  const [editing, setEditing] = useState<{ c: Campaign; isNew: boolean; overwrite?: boolean; key: number } | null>(null);

  const open = (c: Campaign, isNew: boolean, overwrite = false) => {
    setEditing({ c, isNew, overwrite, key: Date.now() });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const list = [...(campaigns.data || [])].sort((a, b) => Number(b.active) - Number(a.active) || b.rate_per_1k - a.rate_per_1k);

  return (
    <div className="mx-auto max-w-5xl">
      <PageHead title="Campañas">
        {!editing && (
          <button type="button" className="btn" onClick={() => open(EMPTY, true)}>
            Nueva a mano
          </button>
        )}
      </PageHead>

      {editing ? (
        <Section title={editing.isNew ? "Revisar y guardar campaña" : `Editar: ${editing.c.name}`}>
          <CampaignEditor
            key={editing.key}
            initial={editing.c}
            isNew={editing.isNew}
            overwrite={editing.overwrite}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setEditing(null);
              campaigns.reload();
            }}
          />
        </Section>
      ) : (
        <Section title="Pegar brief">
          <ExtractBox onDraft={(c, exists) => open(c, true, exists)} />
        </Section>
      )}

      <div className="mt-5">
        <Section title={`Registradas (${list.length})`}>
          {campaigns.error && <ErrorNote>{campaigns.error}</ErrorNote>}
          {list.length === 0 ? (
            <p className="text-sm text-mute">Todavía no hay campañas. Pega el brief de una campaña de Whop arriba.</p>
          ) : (
            <ul>
              {list.map((c) => (
                <li key={c.slug} className="flex flex-wrap items-center justify-between gap-3 border-b border-line py-3 last:border-0">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <span className={`size-2 rounded-full ${c.active ? "bg-st-approved" : "bg-st-draft"}`} aria-hidden />
                      {c.name}
                      {!c.active && <span className="text-[12px] font-normal text-mute">pausada</span>}
                    </p>
                    <p className="text-[13px] text-mute">
                      <span className="num">${c.rate_per_1k}/1K</span> · {c.min_seconds}–{c.max_seconds} s · {c.platforms.map((p) => PLATFORM_LABEL[p]).join(", ")}
                      {c.account ? ` · cuenta ${c.account}` : ""} · {c.source_urls.length} link{c.source_urls.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {c.url && (
                      <a href={c.url} target="_blank" rel="noreferrer" className="btn text-[13px]">
                        Abrir
                      </a>
                    )}
                    <button type="button" className="btn text-[13px]" onClick={() => open(c, false)}>
                      Editar
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}
