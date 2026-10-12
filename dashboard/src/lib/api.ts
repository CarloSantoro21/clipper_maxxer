// Cliente del API local de clipforge (clipforge serve).

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Status = "draft" | "rendered" | "approved" | "rejected" | "published";
export type Platform = "tiktok" | "instagram" | "youtube" | "x";

export const STATUSES: Status[] = ["draft", "rendered", "approved", "rejected", "published"];
export const PLATFORMS: Platform[] = ["tiktok", "instagram", "youtube", "x"];

export const STATUS_LABEL: Record<Status, string> = {
  draft: "Borrador",
  rendered: "Renderizado",
  approved: "Aprobado",
  rejected: "Rechazado",
  published: "Publicado",
};

export interface CaptionStyle {
  preset: "karaoke" | "pop" | "plain";
  font: string;
  size: number;
  color: string;
  highlight: string;
  outline: number;
  position: "center" | "lower" | "upper";
  words_per_line: number;
  uppercase: boolean;
}

export interface Zoom {
  at: number;
  duration: number;
  scale: number;
}

export interface Metrics {
  published_url: string | null;
  platform: Platform | null;
  views: number | null;
  published_at: string | null;
}

interface MediaInfo {
  account: string;
  video_url: string | null;
  thumb_url: string | null;
  rendered_at: number | null;
  caption: string;
}

export interface Clip extends Metrics, MediaInfo {
  kind: "clip";
  id: string;
  job_id: string;
  campaign: string | null;
  source: string;
  start: number;
  end: number;
  duration: number;
  hook: string;
  hook_seconds: number;
  title: string;
  hashtags: string[];
  why: string;
  score: number;
  crop_x: number;
  captions: CaptionStyle;
  zooms: Zoom[];
  status: Status;
  issues: string[];
}

export interface Story extends Metrics, MediaInfo {
  kind: "story";
  id: string;
  title: string;
  hook: string;
  script: string;
  voice: string;
  rate: string;
  background: string | null;
  background_start: number;
  captions: CaptionStyle;
  part: number | null;
  hashtags: string[];
  status: Status;
}

export interface Job {
  job_id: string;
  src: string;
  campaign: string | null;
  title?: string | null;
  channel?: string | null;
  account: string;
  has_transcript: boolean;
  source_duration: number | null;
  clips: Clip[];
  updated_at: number;
}

export interface Campaign {
  slug: string;
  name: string;
  url: string;
  niche: string;
  account: string;
  rate_per_1k: number;
  platforms: Platform[];
  min_seconds: number;
  max_seconds: number;
  language: string;
  source_urls: string[];
  required_hashtags: string[];
  required_mentions: string[];
  required_text: string[];
  banned: string[];
  notes: string;
  active: boolean;
}

export interface Task {
  id: string;
  kind: "clip" | "story" | "render";
  label: string;
  target: Record<string, string | null>;
  status: "queued" | "running" | "done" | "error";
  progress: number;
  step: string;
  log: string[];
  result: Record<string, string>;
  error: string | null;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailToText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body").join(".") : "";
        return loc ? `${loc}: ${d?.msg}` : String(d?.msg ?? d);
      })
      .join(" · ");
  }
  return JSON.stringify(detail);
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `No hay conexión con la API en ${API_URL}. Arráncala con: clipforge serve`);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = detailToText(body.detail ?? body);
    } catch {
      /* respuesta sin JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return (await res.json()) as T;
}

export const send = <T>(method: string, path: string, body?: unknown) =>
  api<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });

export function mediaUrl(path: string | null): string | null {
  return path ? `${API_URL}${path}` : null;
}

export function fmtTime(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec)) return "–";
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

export function fmtDuration(sec: number): string {
  return sec < 60 ? `${Math.round(sec)} s` : `${Math.floor(sec / 60)} min ${Math.round(sec % 60)} s`;
}

export function fmtViews(v: number | null): string {
  if (v == null) return "–";
  return new Intl.NumberFormat("es-MX", { notation: "compact", maximumFractionDigits: 1 }).format(v);
}

// ---------- Chat por SSE ----------

export type ChatEvent =
  | { type: "session"; session_id: string }
  | { type: "text"; text: string }
  | { type: "tool"; name: string; detail: string }
  | { type: "error"; message: string }
  | { type: "done"; session_id: string | null; is_error: boolean; result: string | null };

export interface ChatContext {
  job?: string;
  clip?: string;
  story?: string;
}

/** POST /api/chat y lee el stream SSE (EventSource no soporta POST). */
export async function streamChat(
  body: { message: string; session_id?: string | null; context: ChatContext },
  onEvent: (ev: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let msg = res.statusText;
    try {
      msg = detailToText((await res.json()).detail);
    } catch {
      /* sin JSON */
    }
    throw new ApiError(res.status, msg);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        onEvent({ type: event, ...JSON.parse(data) } as ChatEvent);
      } catch {
        /* bloque incompleto o inválido */
      }
    }
  }
}

/** Evento global: el chat cambió algo, las vistas recargan sus datos. */
export const REFRESH_EVENT = "clipforge:refresh";
export const emitRefresh = () => window.dispatchEvent(new Event(REFRESH_EVENT));
