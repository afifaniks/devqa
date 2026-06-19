import { useMemo, useState } from "react";
import { Text } from "@mantine/core";
import { usePolling } from "../../hooks/usePolling.js";
import { api } from "../../api.js";
import { OUTCOME_ORDER, outcomeOf } from "../../lib/outcomes.js";
import { SectionLabel } from "../SectionLabel.jsx";
import { RunPicker } from "./RunPicker.jsx";
import { FilterBar } from "./FilterBar.jsx";
import { SummaryStrip } from "./SummaryStrip.jsx";
import { CompareGrid } from "./CompareGrid.jsx";

const EMPTY_FILTERS = {
  kt: "all", outcome: "all", repo: "all", search: "",
  onlyDisagree: false, onlyGraded: false,
};

// Browse predictions for several runs side by side. The comparison matrix polls
// live (every 5s) so an in-flight run fills in its column as it answers.
export function CompareView({ runs }) {
  const [selected, setSelected] = useState([]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [openQid, setOpenQid] = useState(null);

  const setF = (k, v) => setFilters(f => ({ ...f, [k]: v }));
  const toggle = name =>
    setSelected(p => (p.includes(name) ? p.filter(x => x !== name) : [...p, name]));

  const key = selected.join(",");
  const { data, loading } = usePolling(
    () => (selected.length ? api.compare(selected) : Promise.resolve(null)),
    selected.length ? 5000 : null,
    [key]
  );

  const sel = data?.runs?.map(r => r.name) ?? [];
  const repos = useMemo(
    () => (data ? [...new Set(data.rows.map(r => r.repo).filter(Boolean))].sort() : []),
    [data]
  );

  const rows = useMemo(() => {
    if (!data) return [];
    return data.rows.filter(row => {
      if (filters.kt !== "all" && row.knowledge_type !== filters.kt) return false;
      if (filters.repo !== "all" && row.repo !== filters.repo) return false;
      const cells = sel.map(rn => row.cells[rn]);
      if (filters.onlyGraded && !cells.some(c => c && c.graded)) return false;
      if (filters.outcome !== "all" && !cells.some(c => outcomeOf(c) === filters.outcome)) return false;
      if (filters.onlyDisagree) {
        const os = [...new Set(cells.filter(c => c && c.graded).map(outcomeOf))];
        if (os.length < 2) return false;
      }
      if (filters.search) {
        const q = filters.search.toLowerCase();
        const hay = `${row.qid} ${row.repo || ""} ${row.title || ""} ${row.question || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [data, filters, key]);

  const tally = useMemo(() => {
    const t = {};
    sel.forEach(rn => { t[rn] = Object.fromEntries(OUTCOME_ORDER.map(o => [o, 0])); });
    rows.forEach(row => sel.forEach(rn => {
      const o = outcomeOf(row.cells[rn]) || "ungraded";
      t[rn][o]++;
    }));
    return t;
  }, [rows, key]);

  return (
    <>
      <SectionLabel mt="xs" count={selected.length ? `${selected.length} selected` : null}>
        Select runs to compare
      </SectionLabel>
      {runs.length === 0
        ? <Text c="dimmed" ta="center" py="xl">No runs found yet.</Text>
        : <RunPicker runs={runs} selected={selected} onToggle={toggle} />}

      {selected.length > 0 && (
        <>
          <SectionLabel>Filters</SectionLabel>
          <FilterBar f={filters} set={setF} repos={repos} />

          {data && sel.length > 0 && <SummaryStrip runs={sel} tally={tally} />}

          <SectionLabel count={`${rows.length} question${rows.length === 1 ? "" : "s"}`}>
            Predictions
          </SectionLabel>

          {data && sel.length > 0 ? (
            <CompareGrid
              rows={rows} runMeta={data.runs} selected={sel}
              openQid={openQid} onToggleRow={setOpenQid}
            />
          ) : (
            <Text c="dimmed" ta="center" py="xl">loading…</Text>
          )}
        </>
      )}

      {selected.length === 0 && (
        <Text c="dimmed" ta="center" py="xl">
          Pick two or more runs above to compare their predictions side by side.
        </Text>
      )}
    </>
  );
}
