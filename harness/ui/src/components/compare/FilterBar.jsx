import { Paper, Group, Select, TextInput, Switch } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { OUTCOME_ORDER } from "../../lib/outcomes.js";

// Filters over the comparison rows. All controlled by the parent so the grid
// and the summary strip stay in sync.
export function FilterBar({ f, set, repos }) {
  return (
    <Paper withBorder p="sm" radius="md" mb="md">
      <Group align="flex-end" gap="lg" wrap="wrap">
        <Select
          label="Knowledge type" w={170} value={f.kt} onChange={v => set("kt", v || "all")}
          data={[
            { value: "all", label: "all" },
            { value: "parametric", label: "parametric" },
            { value: "grounded", label: "contextual" },
          ]}
        />
        <Select
          label="Outcome (any run)" w={170} value={f.outcome} onChange={v => set("outcome", v || "all")}
          data={[{ value: "all", label: "all" }, ...OUTCOME_ORDER.map(o => ({ value: o, label: o }))]}
        />
        <Select
          label="Repo" w={210} searchable value={f.repo} onChange={v => set("repo", v || "all")}
          data={[{ value: "all", label: "all" }, ...repos.map(r => ({ value: r, label: r }))]}
        />
        <TextInput
          label="Search" w={240} value={f.search}
          leftSection={<IconSearch size={14} />}
          placeholder="qid / repo / text"
          onChange={e => set("search", e.currentTarget.value)}
        />
        <Switch
          label="only disagreements" checked={f.onlyDisagree}
          onChange={e => set("onlyDisagree", e.currentTarget.checked)}
        />
        <Switch
          label="only graded" checked={f.onlyGraded}
          onChange={e => set("onlyGraded", e.currentTarget.checked)}
        />
      </Group>
    </Paper>
  );
}
