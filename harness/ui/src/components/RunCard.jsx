import { useState } from "react";
import {
  Paper, Group, Badge, Text, Progress, Box, Collapse, Menu, ActionIcon, Loader,
  Popover, Select, Switch, Button, Stack,
} from "@mantine/core";
import { IconTrash, IconDots, IconGavel } from "@tabler/icons-react";
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

// A small popover to (re-)grade a run: pick the judge, optionally force, launch.
// The grade runs as a tracked process (visible in the Launched-processes list).
function GradeControl({ run, judges, onGraded }) {
  const [opened, setOpened] = useState(false);
  const [judge, setJudge] = useState(judges[0] || "");
  const [force, setForce] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api.gradeRun(run.name, { judge: judge || null, force });
      setOpened(false);
      onGraded?.();
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Popover opened={opened} onChange={setOpened} position="bottom-end" withArrow shadow="md" width={260}>
      <Popover.Target>
        <Button
          size="compact-xs" variant="light" color="azure"
          leftSection={<IconGavel size={13} />}
          onClick={e => { e.stopPropagation(); setOpened(o => !o); }}
        >
          grade
        </Button>
      </Popover.Target>
      <Popover.Dropdown onClick={e => e.stopPropagation()}>
        <Stack gap="sm">
          <Select
            label="Judge model" size="xs" searchable
            data={judges} value={judge} onChange={setJudge}
            placeholder="default (gpt-5.4)"
          />
          <Switch
            size="xs" label="Force re-grade (ignore existing)"
            checked={force} onChange={e => setForce(e.currentTarget.checked)}
          />
          {err && <Text size="xs" c="var(--c-red)">{err}</Text>}
          <Button size="xs" color="azure" loading={busy} onClick={submit}
                  leftSection={<IconGavel size={14} />}>
            {run.n_graded > 0 ? "Re-grade run" : "Grade run"}
          </Button>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

export function RunCard({ run, totals, judges = [], open, onToggle, onDeleted, onGraded }) {
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

  // A run may carry several gradings (one per judge). Pick which to show; default to
  // the most recent (gradings[0]). The selected judge drives the badges + item detail.
  const gradings = run.gradings || [];
  const [judgeSlug, setJudgeSlug] = useState(null);
  const sel = gradings.find(g => g.slug === judgeSlug) || gradings[0] || {};

  // Items poll live only while the card is expanded — no point fetching detail
  // for collapsed runs. usePolling re-creates when name or selected judge changes.
  const { data } = usePolling(
    () => (open ? api.runDetail(run.name, sel.slug) : Promise.resolve({ items: [] })),
    open ? 4000 : null,
    [open, run.name, sel.slug]
  );
  const items = data?.items ?? [];

  const o = sel.outcomes || {};
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
          <Text size="xs" c="dimmed">graded <Text span fw={600} c="bright" ff="monospace">{sel.n_graded || 0}</Text></Text>
          {sel.n_graded > 0 && (
            <Group gap={4}>
              <Badge size="sm" variant="light" color="teal">✓ {o.correct || 0}</Badge>
              <Badge size="sm" variant="light" color="yellow">~ {o.partial || 0}</Badge>
              <Badge size="sm" variant="light" color="red">✗ {o.incorrect || 0}</Badge>
              {sel.n_hallucinated > 0 && (
                <Badge size="sm" variant="light" color="orange">☄ {sel.n_hallucinated}</Badge>
              )}
            </Group>
          )}
          {/* Judge: a selector when the run was graded by more than one judge, else a badge. */}
          {gradings.length > 1 ? (
            <Select
              size="xs" w={190} variant="filled"
              value={sel.slug} onChange={v => setJudgeSlug(v)}
              onClick={e => e.stopPropagation()}
              comboboxProps={{ withinPortal: true }}
              data={gradings.map(g => ({
                value: g.slug,
                label: `judge: ${g.judge_model || g.slug} (${g.n_graded})`,
              }))}
            />
          ) : sel.judge_model && (
            <Badge size="sm" variant="outline"
                   color={sel.judge_model === "mixed" ? "orange" : "gray"}
                   styles={{ root: { textTransform: "none" } }}
                   title="LLM judge used for grading">
              {sel.judge_model === "mixed" ? "⚠ mixed judges" : `judge: ${sel.judge_model}`}
            </Badge>
          )}
          {run.is_agent && Object.keys(run.tool_groups || {}).length > 0 && (
            <Text size="xs" c="dimmed" ff="monospace">
              {Object.entries(run.tool_groups).map(([g, n]) => `${g}:${n}`).join(" ")}
            </Text>
          )}
          <Text size="xs" c="dimmed">{age(run.updated_secs_ago)}</Text>

          {!run.running && <GradeControl run={run} judges={judges} onGraded={onGraded} />}

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
