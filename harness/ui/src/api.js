// Thin, typed wrapper over the harness monitor HTTP API. One function per
// endpoint so components never hand-build URLs or repeat fetch boilerplate.

async function request(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const detail = (await r.json().catch(() => ({}))).detail || r.statusText;
    throw new Error(detail);
  }
  return r.json();
}

const postJSON = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

const q = encodeURIComponent;

export const api = {
  options: () => request("/api/options"),
  benchmark: () => request("/api/benchmark"),
  benchmarkItem: slug => request(`/api/benchmark/item?slug=${q(slug)}`),
  runs: () => request("/api/runs"),
  runDetail: (name, judge) =>
    request(`/api/runs/${q(name)}${judge ? `?judge=${q(judge)}` : ""}`),
  deleteRun: name => request(`/api/runs/${q(name)}`, { method: "DELETE" }),
  compare: names => request(`/api/compare?runs=${names.map(q).join(",")}`),
  transcript: (name, slug) => request(`/api/transcript/${q(name)}/${q(slug)}`),
  live: (name, slug, since = 0) =>
    request(`/api/live/${q(name)}/${q(slug)}?since=${since}`),
  procs: () => request("/api/procs"),
  launch: body => postJSON("/api/launch", body),
  stopProc: id => postJSON(`/api/procs/${q(id)}/stop`, {}),
  removeProc: id => request(`/api/procs/${q(id)}`, { method: "DELETE" }),
  gradeRun: (name, body) => postJSON(`/api/runs/${q(name)}/grade`, body),
};
