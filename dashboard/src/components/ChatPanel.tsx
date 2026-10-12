"use client";

import { useEffect, useRef, useState } from "react";
import { ChatContext, emitRefresh, streamChat } from "@/lib/api";
import { useStored } from "@/lib/hooks";

type Msg =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; tools: { name: string; detail: string }[]; error?: string };

function contextLabel(ctx: ChatContext) {
  if (ctx.clip && ctx.job) return `${ctx.job} / ${ctx.clip}`;
  if (ctx.story) return `story ${ctx.story}`;
  if (ctx.job) return ctx.job;
  return "sin clip abierto";
}

const SUGGESTIONS = [
  "Que empiece 1.5 s después y re-renderiza",
  "Hook más corto y con más curiosidad",
  "Subtítulos verdes, 2 palabras por línea",
];

export default function ChatPanel({ context, onClose }: { context: ChatContext; onClose?: () => void }) {
  const [messages, setMessages] = useStored<Msg[]>("clipforge.chat.messages", []);
  const [sessionId, setSessionId] = useStored<string | null>("clipforge.chat.session", null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setBusy(true);
    let draft: Msg[] = [...messages, { role: "user", text: message }, { role: "assistant", text: "", tools: [] }];
    setMessages(draft);
    const update = (fn: (m: Extract<Msg, { role: "assistant" }>) => Extract<Msg, { role: "assistant" }>) => {
      const last = draft[draft.length - 1] as Extract<Msg, { role: "assistant" }>;
      draft = [...draft.slice(0, -1), fn(last)];
      setMessages(draft);
    };
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await streamChat(
        { message, session_id: sessionId, context },
        (ev) => {
          if (ev.type === "session" && ev.session_id) setSessionId(ev.session_id);
          else if (ev.type === "text") update((m) => ({ ...m, text: m.text + ev.text }));
          else if (ev.type === "tool") update((m) => ({ ...m, tools: [...m.tools, { name: ev.name, detail: ev.detail }] }));
          else if (ev.type === "error") update((m) => ({ ...m, error: ev.message }));
          else if (ev.type === "done") {
            if (ev.session_id) setSessionId(ev.session_id);
            if (ev.is_error) update((m) => ({ ...m, error: ev.result || "Claude devolvió un error" }));
          }
        },
        ac.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") update((m) => ({ ...m, error: (e as Error).message }));
    } finally {
      setBusy(false);
      abortRef.current = null;
      // Claude pudo haber cambiado specs o renders: todas las vistas recargan
      emitRefresh();
    }
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-surface" aria-label="Chat con el orquestador">
      <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-[15px] font-bold text-ink">Orquestador</h2>
          <p className="truncate text-xs text-mute">
            Contexto: <span className="font-medium text-ink">{contextLabel(context)}</span>
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button
            type="button"
            className="btn px-2.5 py-1 text-[13px]"
            disabled={busy || messages.length === 0}
            onClick={() => {
              setMessages([]);
              setSessionId(null);
            }}
          >
            Nueva conversación
          </button>
          {onClose && (
            <button type="button" className="btn px-2.5 py-1 text-[13px]" onClick={onClose} aria-label="Cerrar chat">
              Cerrar
            </button>
          )}
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="space-y-3 text-sm text-mute">
            <p>
              Pídele cambios en lenguaje normal. Claude edita el spec del clip abierto y lo re-renderiza con{" "}
              <code className="text-ink">clipforge</code>.
            </p>
            <div className="flex flex-col items-start gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="btn text-left text-[13px] font-normal" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-8 rounded-lg bg-accent px-3 py-2 text-sm text-accent-ink whitespace-pre-wrap">
              {m.text}
            </div>
          ) : (
            <div key={i} className="space-y-2 text-sm text-ink">
              {m.tools.length > 0 && (
                <ul className="space-y-1">
                  {m.tools.map((t, j) => (
                    <li key={j} className="truncate rounded border border-line bg-sunken px-2 py-1 text-xs text-mute" title={t.detail}>
                      <span className="font-semibold text-ink">{t.name}</span> {t.detail}
                    </li>
                  ))}
                </ul>
              )}
              {m.text ? (
                <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
              ) : (
                busy && i === messages.length - 1 && !m.error && <p className="text-mute">Pensando…</p>
              )}
              {m.error && <p className="rounded border border-st-rejected/40 bg-st-rejected/10 px-2 py-1 text-xs">{m.error}</p>}
            </div>
          ),
        )}
        <div ref={endRef} />
      </div>

      <form
        className="border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Mensaje para el orquestador
        </label>
        <textarea
          id="chat-input"
          className="field min-h-[72px] resize-none text-sm"
          placeholder="Ej.: corta los últimos 3 segundos"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <span className="text-xs text-mute">Enter envía; Shift+Enter, salto de línea</span>
          {busy ? (
            <button type="button" className="btn" onClick={() => abortRef.current?.abort()}>
              Detener
            </button>
          ) : (
            <button type="submit" className="btn btn-primary" disabled={!input.trim()}>
              Enviar
            </button>
          )}
        </div>
      </form>
    </section>
  );
}
