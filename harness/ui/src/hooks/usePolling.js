import { useCallback, useEffect, useRef, useState } from "react";

// Live data the simple, robust way: fetch on mount, then re-fetch on an
// interval. Pauses while the tab is hidden (no point polling a backgrounded
// dashboard) and resumes — with an immediate fetch — when it returns. Keeps the
// last good value through transient errors so the view never blanks out.
//
//   const { data, error, loading, refresh } = usePolling(api.runs, 3000, []);
//
// `deps` re-creates the poller when its inputs change (e.g. selected run name).
export function usePolling(fetcher, intervalMs, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const savedFetcher = useRef(fetcher);
  savedFetcher.current = fetcher;

  const refresh = useCallback(async () => {
    try {
      const d = await savedFetcher.current();
      if (alive.current) { setData(d); setError(null); }
    } catch (e) {
      if (alive.current) setError(e);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    setLoading(true);
    refresh();

    let timer = null;
    const start = () => { if (!timer && intervalMs) timer = setInterval(refresh, intervalMs); };
    const stop = () => { if (timer) { clearInterval(timer); timer = null; } };
    const onVisibility = () => {
      if (document.hidden) stop();
      else { refresh(); start(); }
    };

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      alive.current = false;
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);

  return { data, error, loading, refresh };
}
