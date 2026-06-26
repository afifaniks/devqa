import { useState } from "react";
import {
  Paper, Group, Badge, Text, Progress, Box, Collapse, Menu, ActionIcon, Loader,
} from "@mantine/core";
import { IconTrash, IconDots } from "@tabler/icons-react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { age, pct } from "../lib/format.js";
import { dominantOutcome } from "../lib/outcomes.js";
import { VERDICT_COLOR } from "../theme.js";
import { RunItem } from "./RunItem.jsx";

const SPINE = {
  correct: "var(--mantine-color-teal-5)",
  partial: "var(--mantine-color-yellow-5)",
  incorrect: "var(--mantine-color-red-5)",
};

export function RunCard({ run, totals, open, onToggle, onDeleted }) {
  const [deleting, setDeleting] = useState(false);
  const [delErr, setDelErr] = useState(null);

  const handleDelete = async () => {
    setDeleting(true);
    setDelErr(null);
    try {
      await api.deleteRun(run.name);
      onDeleted?.(run.name);
    } catch (e) {
      setDelErr(String(e.message || e));
      setDeleting(false);
    }
  };

  // Items poll live only while the card is expanded — no point fetching detail
  // for collapsed runs. usePolling re-creates when the run name changes.
  const { data } = usePolling(
    () => (open ? api.runDetail(run.name) : Promise.resolve({ items: [] })),
    open ? 4000 : null,
    [open, run.name]
  );
  const items = data?.items ?? [];

  const o = run.outcomes || {};
  const dom = run.running ? "running" : dominantOutcome(
    Object.entries(o).flatMap(([k, n]) => Array(n).fill({ graded: true, outcome: k }))
  );
  const spine = run.running ? "var(--mantine-color-teal-5)" : SPINE[dom];

  return (
    <Paper
      withBorder radius="md" className="verdict-spine" mb="sm"
      style={{ "--spine-color": spine, overflow: "hidden" }}
    >
      <Group gap="sm" px="md" py="sm" wrap="wrap"
             style={{ cursor: "pointer" }} onClick={() => onToggle(run.name)}>
        <Badge color={run.running ? "teal" : "gray"} variant={run.running ? "filled" : "light"} size="sm">
          {run.running ? "live" : "idle"}
        </Badge>
        {run.is_agent && <Badge color="violet" variant="light" size="sm">agent</Badge>}
        <Text ff="monospace" fw={600} size="sm">{run.name}</Text>

        <Group gap="lg" ml="auto" wrap="wrap">
          <Text size="xs" c="dimmed">done <Text span fw={600} c="bright" ff="monospace">{run.n_done}</Text></Text>
          {run.n_errors > 0 && (
            <Text size="xs" c="dimmed">errors <Text span fw={600} c="var(--c-red)" ff="monospace">{run.n_errors}</Text></Text>
          )}
          <Text size="xs" c="dimmed">graded <Text span fw={600} c="bright" ff="monospace">{run.n_graded}</Text></Text>
          {run.n_graded > 0 && (
            <Group gap={4}>
              <Badge size="sm" variant="light" color="teal">✓ {o.correct || 0}</Badge>
              <Badge size="sm" variant="light" color="yellow">~ {o.partial || 0}</Badge>
              <Badge size="sm" variant="light" color="red">✗ {o.incorrect || 0}</Badge>
              {run.n_hallucinated > 0 && (
                <Badge size="sm" variant="light" color="pink">☄ {run.n_hallucinated}</Badge>
              )}
            </Group>
          )}
          {run.is_agent && Object.keys(run.tool_groups || {}).length > 0 && (
            <Text size="xs" c="dimmed" ff="monospace">
              {Object.entries(run.tool_groups).map(([g, n]) => `${g}:${n}`).join(" ")}
            </Text>
          )}
          <Text size="xs" c="dimmed">{age(run.updated_secs_ago)}</Text>

          {delErr && <Text size="xs" c="var(--c-red)" maw={220} truncate title={delErr}>{delErr}</Text>}
          {deleting ? (
            <Loader size="xs" color="red" />
          ) : (
            <Menu shadow="md" position="bottom-end" withinPortal>
              <Menu.Target>
                <ActionIcon
                  variant="subtle" color="gray" size="sm"
                  aria-label="Run actions"
                  onClick={e => e.stopPropagation()}
                >
                  <IconDots size={16} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown onClick={e => e.stopPropagation()}>
                <Menu.Label>{run.running ? "Run looks active" : "Delete run files"}</Menu.Label>
                <Menu.Item
                  color="red" leftSection={<IconTrash size={14} />}
                  disabled={run.running}
                  onClick={e => { e.stopPropagation(); handleDelete(); }}
                >
                  Delete run
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>
      </Group>

      <Progress
        value={pct(run.n_done, totals.items_approved)}
        size="xs" radius={0} color={run.running ? "azure" : "gray.5"}
        transitionDuration={500}
      />

      <Collapse in={open}>
        <Box style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
          {items.length === 0
            ? <Text size="sm" c="dimmed" ta="center" py="md">loading items…</Text>
            : items.map(it => <RunItem key={it.qid} run={run} it={it} />)}
        </Box>
      </Collapse>
    </Paper>
  );
}
