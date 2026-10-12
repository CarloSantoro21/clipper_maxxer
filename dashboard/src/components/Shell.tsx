"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ChatContext } from "@/lib/api";
import { useStored } from "@/lib/hooks";
import ChatPanel from "./ChatPanel";

const NAV = [
  { href: "/", label: "Revisión" },
  { href: "/nuevo", label: "Nuevo" },
  { href: "/campanas", label: "Campañas" },
];

type Theme = "auto" | "light" | "dark";
const THEME_LABEL: Record<Theme, string> = { auto: "Tema: auto", light: "Tema: claro", dark: "Tema: oscuro" };
const NEXT_THEME: Record<Theme, Theme> = { auto: "light", light: "dark", dark: "auto" };

function contextFrom(pathname: string): ChatContext {
  const parts = pathname.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "clip" && parts[1]) return { job: parts[1], clip: parts[2] };
  if (parts[0] === "story" && parts[1]) return { story: parts[1] };
  return {};
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [theme, setTheme] = useStored<Theme>("clipforge.theme", "auto");
  const [chatOpen, setChatOpen] = useStored<boolean>("clipforge.chat.open", false);
  const [mobileChat, setMobileChat] = useState(false);
  const context = contextFrom(pathname);

  const cycleTheme = () => {
    const next = NEXT_THEME[theme];
    setTheme(next);
    const root = document.documentElement;
    if (next === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", next);
  };

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="flex h-14 items-center gap-4 px-4 lg:px-6">
          <Link href="/" className="flex items-center gap-2 text-[17px] font-extrabold tracking-[-0.02em] text-ink">
            <span className="grid h-6 w-[14px] place-items-center rounded-[3px] bg-ink" aria-hidden>
              <span className="h-2 w-[6px] rounded-[1px] bg-st-rejected" />
            </span>
            clipforge
          </Link>
          <nav className="hidden items-center gap-1 sm:flex" aria-label="Secciones">
            {NAV.map((n) => {
              const active = n.href === "/" ? pathname === "/" || pathname.startsWith("/clip") || pathname.startsWith("/story") : pathname.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-md px-3 py-1.5 text-sm font-semibold ${active ? "bg-sunken text-ink" : "text-mute hover:text-ink"}`}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" className="btn px-2.5 text-[13px]" onClick={cycleTheme}>
              {THEME_LABEL[theme]}
            </button>
            <button
              type="button"
              className={`btn hidden px-2.5 text-[13px] lg:inline-flex ${chatOpen ? "btn-primary" : ""}`}
              aria-pressed={chatOpen}
              onClick={() => setChatOpen(!chatOpen)}
            >
              Chat
            </button>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 px-4 pb-24 pt-6 sm:pb-10 lg:px-6">{children}</main>
        {chatOpen && (
          <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-[380px] shrink-0 border-l border-line lg:block">
            <ChatPanel context={context} onClose={() => setChatOpen(false)} />
          </aside>
        )}
      </div>

      {/* Móvil y tablet: barra inferior con pestañas, el chat abre a pantalla completa */}
      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-surface sm:hidden" aria-label="Secciones">
        {NAV.map((n) => {
          const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={`py-3 text-center text-[13px] font-semibold ${active ? "text-accent" : "text-mute"}`}
            >
              {n.label}
            </Link>
          );
        })}
        <button type="button" className="py-3 text-center text-[13px] font-semibold text-mute" onClick={() => setMobileChat(true)}>
          Chat
        </button>
      </nav>
      <button
        type="button"
        className="btn btn-primary fixed bottom-5 right-5 z-30 hidden shadow-lg sm:inline-flex lg:hidden"
        onClick={() => setMobileChat(true)}
      >
        Chat
      </button>
      {mobileChat && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Chat">
          <ChatPanel context={context} onClose={() => setMobileChat(false)} />
        </div>
      )}
    </div>
  );
}
