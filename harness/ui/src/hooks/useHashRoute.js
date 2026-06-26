import { useSyncExternalStore, useCallback } from "react";

// Hash-based routing — no dependency, no server SPA-fallback needed (the monitor
// serves index.html at "/" only). The hash encodes the active tab and, on the
// benchmark tab, the open QA pair:
//
//   #/benchmark                      → benchmark list
//   #/benchmark/<slug>               → one QA pair detail; slug is the readable
//                                       owner_repo_<number>_q<k> id from the API
//   #/monitor  | #/compare           → other tabs
//
// Every QA pair therefore has a unique, shareable URL.

const TABS = new Set(["benchmark", "monitor", "compare"]);

function parse(hash) {
  const raw = (hash || "").replace(/^#\/?/, "");
  const [tabSeg, slugSeg] = raw.split("/");
  const tab = TABS.has(tabSeg) ? tabSeg : "benchmark";
  const slug = tab === "benchmark" && slugSeg ? decodeURIComponent(slugSeg) : null;
  return { tab, slug };
}

export function routeHash({ tab, slug }) {
  return slug ? `#/${tab}/${encodeURIComponent(slug)}` : `#/${tab}`;
}

const subscribe = cb => {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
};
const snapshot = () => window.location.hash;

export function useHashRoute() {
  const hash = useSyncExternalStore(subscribe, snapshot);
  const route = parse(hash);

  const navigate = useCallback(next => {
    const target = routeHash(next);
    if (window.location.hash !== target) window.location.hash = target;
  }, []);

  return { route, navigate };
}
