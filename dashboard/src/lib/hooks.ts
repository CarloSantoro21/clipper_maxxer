"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { REFRESH_EVENT, Task, api } from "./api";

/** GET con recarga manual, recarga al volver a la pestaña y recarga cuando el chat cambia algo. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const pathRef = useRef(path);

  const reload = useCallback(async () => {
    const p = pathRef.current;
    if (!p) return;
    try {
      const d = await api<T>(p);
      if (pathRef.current === p) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (pathRef.current === p) setError((e as Error).message);
    } finally {
      if (pathRef.current === p) setLoading(false);
    }
  }, []);

  useEffect(() => {
    pathRef.current = path;
    if (!path) return;
    // la carga inicial se dispara desde el efecto, no durante el render
    const t = setTimeout(reload, 0);
    const onFocus = () => document.visibilityState === "visible" && reload();
    window.addEventListener(REFRESH_EVENT, reload);
    document.addEventListener("visibilitychange", onFocus);
    return () => {
      clearTimeout(t);
      window.removeEventListener(REFRESH_EVENT, reload);
      document.removeEventListener("visibilitychange", onFocus);
    };
  }, [path, reload]);

  return { data, setData, error, loading, reload };
}

/** Sigue una tarea de la cola hasta que termine; llama onDone al acabar bien. */
export function useTask(onDone?: (t: Task) => void) {
  const [task, setTask] = useState<Task | null>(null);
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  });

  useEffect(() => {
    if (!task || task.status === "done" || task.status === "error") return;
    const id = task.id;
    const timer = setTimeout(async () => {
      try {
        const t = await api<Task>(`/api/tasks/${id}`);
        setTask(t);
        if (t.status === "done") doneRef.current?.(t);
      } catch {
        // la API se reinició: la tarea ya no existe
        setTask((prev) => (prev ? { ...prev, status: "error", error: "Se perdió la conexión con la API" } : prev));
      }
    }, 900);
    return () => clearTimeout(timer);
  }, [task]);

  return { task, track: setTask };
}

/** Estado persistido en localStorage (sólo comodidad por navegador). */
export function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(key);
      // sincroniza con lo guardado al montar (no existe en el servidor)
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (raw != null) setValue(JSON.parse(raw) as T);
    } catch {
      /* sin storage */
    }
  }, [key]);
  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        localStorage.setItem(key, JSON.stringify(v));
      } catch {
        /* sin storage */
      }
    },
    [key],
  );
  return [value, set] as const;
}
