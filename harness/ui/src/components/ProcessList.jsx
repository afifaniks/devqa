import {
  Paper, Group, Badge, Text, Button, Collapse, Code, Stack, Loader, Progress,
  ActionIcon, Tooltip, Box,
} from "@mantine/core";
import { IconChevronRight, IconChevronDown, IconPlayerStop, IconTrash } from "@tabler/icons-react";
import { useState } from "react";
import { fmtStamp } from "../lib/format.js";

const PHASE_LABEL = { answering: "answering", grading: "grading", done: "finishing" };

// Live view of processes this UI launched. The log tail + progress are polled by the
// parent (App → /api/procs every 3s); a running evaluation updates in place. Each card
// shows which item is in flight, a progress bar, and a stop/remove control.
function ProcessCard({ p, onStop, onRemove }) {
  const [open, setOpen] = useState(p.running);
  const status = p.running
    ? { color: "teal", label: PHASE_LABEL[p.phase] || "running" }
    : p.returncode === 0
    ? { color: "gray", label: "done" }
    : { color: "red", label: `exit ${p.returncode}` };

  const grading = p.phase === "grading";
  const total = p.total || null;
  const live = p.live_done ?? 0;
  const pct = total ? Math.min(100, (live / total) * 100) : (p.running ? 100 : 0);
  const barColor = grading ? "azure" : "teal";

  return (
    <Paper withBorder p="sm" radius="md">
      <Group gap="sm" wrap="nowrap" align="center"
             onClick={() => setOpen(o => !o)} style={{ cursor: "pointer" }}>
        {open ? <IconChevronDown size={15} /> : <IconChevronRight size={15} />}
        {p.running
          ? <Loader size={14} color="teal" />
          : <Badge color={status.color} variant="light" size="sm">{status.label}</Badge>}

        <Box style={{ minWidth: 0, flex: 1 }}>
          <Group gap={8} wrap="nowrap">
            <Text ff="monospace" fw={600} size="sm" truncate>{p.run_name}</Text>
            {p.running && (
              <Badge color={barColor} variant="light" size="xs">{status.label}</Badge>
            )}
            {/* once answers are in, keep the answered count as a static chip */}
            {p.answered > 0 && (grading || !p.running) && (
              <Badge color="teal" variant="light" size="xs">✓ {p.answered} answered</Badge>
            )}
            <Text size="xs" c="dimmed" style={{ flex: "none" }} title={p.started}>{fmtStamp(p.started)}</Text>
          </Group>
          {p.running && (
            <Group gap={8} wrap="nowrap" mt={3}>
              {p.current_qid && (
                <Text size="xs" c="dimmed" ff="monospace" truncate title={p.current_qid}>
                  {grading ? "⚖" : "▶"} {p.current_qid}
                </Text>
              )}
              {total != null && (
                <Text size="xs" c={grading ? "azure" : "dimmed"} ff="monospace"
                      fw={grading ? 600 : 400} style={{ flex: "none" }} ml="auto">
                  {grading ? "grading " : ""}{live} / {total}
                </Text>
              )}
            </Group>
          )}
        </Box>

        {p.running ? (
          <Button
            size="compact-xs" variant="subtle" color="red" style={{ flex: "none" }}
            leftSection={<IconPlayerStop size={13} />}
            onClick={e => { e.stopPropagation(); onStop(p.proc_id); }}
          >
            stop
          </Button>
        ) : (
          <Tooltip label="Remove from list" openDelay={300}>
            <ActionIcon
              size="sm" variant="subtle" color="gray" style={{ flex: "none" }}
              aria-label="Remove process"
              onClick={e => { e.stopPropagation(); onRemove?.(p.proc_id); }}
            >
              <IconTrash size={14} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>

      {p.running && total != null && (
        <Progress value={pct} size="xs" radius={0} mt="sm" color={barColor} transitionDuration={400} />
      )}

      <Collapse in={open}>
        <Code
          block mt="sm"
          style={{ fontSize: 11, maxHeight: 260, overflow: "auto", whiteSpace: "pre-wrap" }}
        >
          {p.log_tail || "(no output yet)"}
        </Code>
      </Collapse>
    </Paper>
  );
}

export function ProcessList({ procs, onStop, onRemove }) {
  if (!procs?.length) return null;
  return (
    <Stack gap="xs">
      {procs.map(p => <ProcessCard key={p.proc_id} p={p} onStop={onStop} onRemove={onRemove} />)}
    </Stack>
  );
}
