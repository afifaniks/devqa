import { Paper, Group, Badge, Text, Button, Collapse, Code, Stack } from "@mantine/core";
import { IconChevronRight, IconChevronDown, IconPlayerStop } from "@tabler/icons-react";
import { useState } from "react";

// Live view of processes this UI launched. The log tail is polled by the parent
// (App → /api/procs every 3s) and streamed into a scrolling <Code> block, so a
// running evaluation updates in place.
function ProcessCard({ p, onStop }) {
  const [open, setOpen] = useState(p.running);
  const status = p.running
    ? { color: "teal", label: "running" }
    : p.returncode === 0
    ? { color: "gray", label: "done" }
    : { color: "red", label: `exit ${p.returncode}` };

  return (
    <Paper withBorder p="sm" radius="md">
      <Group gap="sm" wrap="nowrap" onClick={() => setOpen(o => !o)} style={{ cursor: "pointer" }}>
        {open ? <IconChevronDown size={15} /> : <IconChevronRight size={15} />}
        <Badge color={status.color} variant="light" size="sm"
               leftSection={p.running ? "●" : null}>
          {status.label}
        </Badge>
        <Text ff="monospace" fw={600} size="sm">{p.run_name}</Text>
        <Text size="xs" c="dimmed">{p.started}</Text>
        {p.running && (
          <Button
            ml="auto" size="compact-xs" variant="subtle" color="red"
            leftSection={<IconPlayerStop size={13} />}
            onClick={e => { e.stopPropagation(); onStop(p.proc_id); }}
          >
            stop
          </Button>
        )}
      </Group>
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

export function ProcessList({ procs, onStop }) {
  if (!procs?.length) return null;
  return (
    <Stack gap="xs">
      {procs.map(p => <ProcessCard key={p.proc_id} p={p} onStop={onStop} />)}
    </Stack>
  );
}
