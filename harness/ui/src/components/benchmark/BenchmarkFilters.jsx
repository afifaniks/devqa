import { Paper, Group, TextInput, Select, Switch } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { ktLabel } from "../../lib/benchmark.js";

const opt = (all, xs, label = x => x) =>
  [{ value: "all", label: all }, ...xs.map(x => ({ value: x, label: label(x) }))];

// Filters over the QA-pair list. Controlled by the parent so the table + count stay in sync.
export function BenchmarkFilters({ f, set, facets }) {
  return (
    <Paper withBorder p="sm" radius="md" mb="md">
      <Group align="flex-end" gap="md" wrap="wrap">
        <TextInput
          label="Search" w={260} value={f.search}
          leftSection={<IconSearch size={14} />}
          placeholder="qid / repo / title / question"
          onChange={e => set("search", e.currentTarget.value)}
        />
        <Select label="Repo" w={200} searchable value={f.repo}
                onChange={v => set("repo", v || "all")} data={opt("all repos", facets.repos || [])} />
        <Select label="Knowledge type" w={160} value={f.kt}
                onChange={v => set("kt", v || "all")} data={opt("all", facets.knowledge_types || [], ktLabel)} />
        <Select label="Artifact" w={180} searchable value={f.artifact}
                onChange={v => set("artifact", v || "all")} data={opt("any", facets.artifacts || [])} />
        <Switch label="has CVE/GHSA/CWE/OSV" checked={f.onlyId}
                onChange={e => set("onlyId", e.currentTarget.checked)} />
      </Group>
    </Paper>
  );
}
