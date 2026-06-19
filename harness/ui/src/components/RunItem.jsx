import { useState } from "react";
import {
  Paper, Group, Badge, Text, Code, Stack, Collapse, Button, Box, Divider,
} from "@mantine/core";
import { IconChevronRight, IconChevronDown } from "@tabler/icons-react";
import { api } from "../api.js";
import { VERDICT_COLOR } from "../theme.js";
import { claimColor } from "../lib/outcomes.js";
import { FactChips } from "./FactChips.jsx";

function Panel({ title, action, children }) {
  return (
    <Paper bg="dark.6" p="sm" radius="sm" withBorder>
      <Group justify="space-between" mb={6}>
        <Text size="xs" tt="uppercase" fw={600} c="dimmed" lh={1}>{title}</Text>
        {action}
      </Group>
      {children}
    </Paper>
  );
}

const pre = {
  whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12,
  maxHeight: 340, overflow: "auto",
};

export function RunItem({ run, it }) {
  const [open, setOpen] = useState(false);
  const [transcript, setTranscript] = useState(null);

  const loadTranscript = async () => {
    try { setTranscript(await api.transcript(run.name, it.qid_slug)); }
    catch { setTranscript({ transcript: [{ step: 0, type: "no transcript found" }] }); }
  };

  return (
    <Box style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
      <Group gap="sm" px="md" py="sm" wrap="wrap"
             style={{ cursor: "pointer" }} onClick={() => setOpen(o => !o)}>
        {open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        <Text ff="monospace" size="xs" c="azure.3">{it.qid}</Text>
        {it.outcome && (
          <Badge size="sm" variant="light" color={VERDICT_COLOR[it.outcome] || "gray"}>
            {it.outcome}
          </Badge>
        )}
        {it.hallucinated && <Badge size="sm" variant="light" color="pink">hallucinated</Badge>}
        {it.error && <Badge size="sm" variant="light" color="red">error</Badge>}
        <Text size="xs" c="dimmed">{it.knowledge_type}</Text>
        {it.n_tool_calls != null && <Text size="xs" c="dimmed">{it.n_tool_calls} tool calls</Text>}
        {it.runtime_secs != null && <Text size="xs" c="dimmed">{it.runtime_secs}s</Text>}
        <Text size="xs" c="dimmed" ml="auto">{it.chars} chars</Text>
      </Group>

      <Collapse in={open}>
        <Stack gap="xs" px="md" pb="md">
          {it.error && (
            <Panel title="Error"><Code block c="red" style={pre}>{it.error}</Code></Panel>
          )}
          <Panel title="Question"><Code block style={pre}>{it.question}</Code></Panel>
          <Panel title="Response"><Code block style={pre}>{it.response}</Code></Panel>

          {it.hard_facts?.length > 0 && (
            <Panel title="Hard facts (deterministic tier)">
              <FactChips facts={it.hard_facts} />
            </Panel>
          )}

          {it.claims?.length > 0 && (
            <Panel title="Judge claims">
              <Stack gap={6}>
                {it.claims.map((c, i) => (
                  <Group key={i} gap={8} align="baseline" wrap="nowrap">
                    <Badge size="sm" variant="light" color={claimColor(c.verdict)}>{c.verdict}</Badge>
                    <Text size="sm" c="dimmed">{c.claim}</Text>
                  </Group>
                ))}
                {(it.hallucinations || []).map((h, i) => (
                  <Group key={`h${i}`} gap={8} align="baseline" wrap="nowrap">
                    <Badge size="sm" variant="light" color="pink">halluc</Badge>
                    <Text size="sm" c="dimmed">{h.assertion || String(h)}</Text>
                  </Group>
                ))}
              </Stack>
            </Panel>
          )}

          {run.is_agent && !it.error && (
            <Panel
              title="Transcript"
              action={<Button size="compact-xs" variant="subtle" onClick={loadTranscript}>load</Button>}
            >
              {transcript ? (
                <Stack gap={4}>
                  {(transcript.transcript || []).map((s, i) => (
                    <Box key={i} pl="sm" style={{ borderLeft: "2px solid var(--mantine-color-dark-3)" }}>
                      <Text ff="monospace" size="xs" fw={600}>
                        #{s.step} {s.type === "tool" ? `${s.tool} ${JSON.stringify(s.args)}` : s.type}
                      </Text>
                      {s.result && <Code block style={{ ...pre, maxHeight: 200 }}>{s.result}</Code>}
                      {s.stdout && <Code block style={{ ...pre, maxHeight: 200 }}>{s.stdout}</Code>}
                    </Box>
                  ))}
                  {transcript.stderr && (
                    <><Divider my={4} /><Code block c="orange" style={pre}>{transcript.stderr}</Code></>
                  )}
                </Stack>
              ) : (
                <Text size="xs" c="dimmed">Click “load” to fetch the agent transcript.</Text>
              )}
            </Panel>
          )}
        </Stack>
      </Collapse>
    </Box>
  );
}
