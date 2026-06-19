import { useEffect, useMemo, useState } from "react";
import { Text, Loader, Group, Pagination, Center } from "@mantine/core";
import { api } from "../../api.js";
import { SectionLabel } from "../SectionLabel.jsx";
import { BenchmarkOverview } from "./BenchmarkOverview.jsx";
import { BenchmarkFilters } from "./BenchmarkFilters.jsx";
import { BenchmarkTable } from "./BenchmarkTable.jsx";
import { BenchmarkDetail } from "./BenchmarkDetail.jsx";

const EMPTY = { search: "", repo: "all", kt: "all", artifact: "all", onlyId: false };
const PAGE_SIZE = 25;

// The released benchmark, browsable: a dataset overview + filterable list of QA pairs;
// clicking a row opens a full detail/reading view. The data is static, so it's fetched
// once (not polled).
export function BenchmarkView() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [openQid, setOpenQid] = useState(null);

  useEffect(() => {
    api.benchmark().then(setData).catch(e => setErr(String(e.message || e)));
  }, []);

  const setF = (k, v) => { setFilters(f => ({ ...f, [k]: v })); setPage(1); };

  const items = data?.items ?? [];
  const filtered = useMemo(() => items.filter(it => {
    if (filters.repo !== "all" && it.repo !== filters.repo) return false;
    if (filters.kt !== "all" && it.knowledge_type !== filters.kt) return false;
    if (filters.artifact !== "all" && !(it.artifacts_needed || []).includes(filters.artifact)) return false;
    if (filters.onlyId && !it.has_hard_id) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const hay = `${it.qid} ${it.repo} ${it.title || ""} ${it.security_topic || ""} ${it.question || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }), [items, filters]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  if (openQid) return <BenchmarkDetail qid={openQid} onBack={() => setOpenQid(null)} />;

  if (err) return <Text c="red.4" ta="center" py="xl">{err}</Text>;
  if (!data) return <Center py={60}><Loader /></Center>;

  return (
    <>
      <SectionLabel mt="xs" count={`${data.count} pairs`}>Benchmark overview</SectionLabel>
      <BenchmarkOverview items={items} facets={data.facets} />

      <SectionLabel>Filter</SectionLabel>
      <BenchmarkFilters f={filters} set={setF} facets={data.facets} />

      <SectionLabel count={`${filtered.length} of ${data.count}`}>QA pairs</SectionLabel>
      <BenchmarkTable items={pageItems} onOpen={setOpenQid} />

      {pageCount > 1 && (
        <Group justify="center" mt="md">
          <Pagination total={pageCount} value={page} onChange={setPage} size="sm" />
        </Group>
      )}
      {filtered.length === 0 && <Text c="dimmed" ta="center" py="xl">No QA pairs match the filters.</Text>}
    </>
  );
}
