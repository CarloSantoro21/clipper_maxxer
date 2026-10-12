"use client";

import Link from "next/link";
import { useMemo } from "react";
import ReviewCard, { Item } from "@/components/ReviewCard";
import { ErrorNote, PageHead, TALLY } from "@/components/ui";
import { Job, STATUSES, STATUS_LABEL, Status, Story } from "@/lib/api";
import { useApi, useStored } from "@/lib/hooks";

type Filter = Status | "all";

export default function ReviewPage() {
  const jobs = useApi<Job[]>("/api/jobs");
  const stories = useApi<Story[]>("/api/stories");
  const [status, setStatus] = useStored<Filter>("clipforge.filter.status", "all");
  const [account, setAccount] = useStored<string>("clipforge.filter.account", "");
  const items: Item[] = useMemo(
    () => [...(jobs.data ?? []).flatMap((j) => j.clips), ...(stories.data ?? [])],
    [jobs.data, stories.data],
  );

  // actualiza en sitio el item que cambió (sin recargar todo)
  function replace(n: Item) {
    if (n.kind === "clip") {
      jobs.setData((js) =>
        (js ?? []).map((j) => (j.job_id === n.job_id ? { ...j, clips: j.clips.map((c) => (c.id === n.id ? n : c)) } : j)),
      );
    } else {
      stories.setData((ss) => (ss ?? []).map((s) => (s.id === n.id ? n : s)));
    }
  }

  const accounts = useMemo(() => [...new Set(items.map((i) => i.account).filter(Boolean))].sort(), [items]);
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: 0 };
    for (const it of items) {
      if (account && it.account !== account) continue;
      c.all++;
      c[it.status] = (c[it.status] ?? 0) + 1;
    }
    return c;
  }, [items, account]);

  const visible = items
    .filter((it) => (status === "all" ? it.status !== "rejected" : it.status === status))
    .filter((it) => !account || it.account === account)
    .sort((a, b) => (b.rendered_at ?? 0) - (a.rendered_at ?? 0) || (b.kind === "clip" ? b.score : 0) - (a.kind === "clip" ? a.score : 0));

  const loading = jobs.loading || stories.loading;
  const error = jobs.error || stories.error;

  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHead title="Revisión">
        <label className="flex items-center gap-2 text-sm text-mute">
          Cuenta
          <select className="field w-auto py-1.5" value={account} onChange={(e) => setAccount(e.target.value)}>
            <option value="">Todas</option>
            {accounts.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
      </PageHead>

      <div className="-mx-4 mb-5 overflow-x-auto px-4" role="tablist" aria-label="Filtrar por estado">
        <div className="flex w-max gap-1.5">
          {(["all", ...STATUSES] as Filter[]).map((s) => {
            const active = status === s;
            return (
              <button
                key={s}
                role="tab"
                aria-selected={active}
                type="button"
                onClick={() => setStatus(s)}
                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] font-semibold ${
                  active ? "border-ink bg-ink text-bg" : "border-line bg-surface text-mute hover:text-ink"
                }`}
              >
                {s !== "all" && <span className={`size-2 rounded-full ${TALLY[s]}`} aria-hidden />}
                {s === "all" ? "Por revisar" : STATUS_LABEL[s]}
                <span className="num opacity-70">{s === "all" ? (counts.all ?? 0) - (counts.rejected ?? 0) : counts[s] ?? 0}</span>
              </button>
            );
          })}
        </div>
      </div>

      <ErrorNote>{error}</ErrorNote>

      {loading && !items.length ? (
        <p className="text-mute">Cargando clips…</p>
      ) : visible.length === 0 && !error ? (
        <div className="rounded-lg border border-dashed border-line px-6 py-12 text-center">
          <p className="font-semibold text-ink">{items.length ? "Nada con este filtro." : "Todavía no hay clips."}</p>
          <p className="mt-1 text-sm text-mute">
            {items.length ? "Cambia el estado o la cuenta arriba." : "Pega un link de campaña o escribe una premisa de story para empezar."}
          </p>
          {!items.length && (
            <Link href="/nuevo" className="btn btn-primary mt-4">
              Crear clips
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(230px,1fr))] gap-4">
          {visible.map((it) => (
            <ReviewCard key={key(it)} item={it} onChange={replace} />
          ))}
        </div>
      )}
    </div>
  );
}

function key(it: Item) {
  return it.kind === "clip" ? `c:${it.job_id}/${it.id}` : `s:${it.id}`;
}
