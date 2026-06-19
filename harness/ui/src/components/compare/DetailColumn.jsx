import { useState } from "react";
import { Paper, Group, Badge, Text, Code, Stack, Button, Box } from "@mantine/core";
import { api } from "../../api.js";
import { VERDICT_COLOR } from "../../theme.js";
import { outcomeOf, claimColor } from "../../lib/outcomes.js";
import { FactChips } from "../FactChips.jsx";

const pre = { whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12, maxHeight: 320, overflow: "auto" };

// One run's full prediction for a question: response, deterministic hard-fact
// tier, judge claims, hallucinations, and (for agents) the tool transcript.
export function DetailColumn({ runName, cell, qidSlug }) {
  const [tr, setTr] = useState(null);

  if (!cell) {
    return (
      <Paper withBorder p="sm" radius="md" bg="dark.7">
        <Text ff="monospace" size="xs" fw={600} mb={6}>{runName}</Text>
        <Text size="xs" c="dimmed" fs="italic">— not answered in this run —</Text>
      </Paper>
    );
  }

  const o = outcomeOf(cell);
  const loadTr = async () => {
    try { setTr(await api.transcript(runName, qidSlug)); }
    catch { setTr({ transcript: [{ step: 0, type: "no transcript found" }] }); }
  };

  return (
    <Paper withBorder p="sm" radius="md" bg="dark.7">
      <Text ff="monospace" size="xs" fw={600} mb={8}>{runName}</Text>

      <Group gap={6} mb={8}>
        <Badge size="sm" variant="light" color={VERDICT_COLOR[o] || "gray"}>{o}</Badge>
        {cell.hallucinated && <Badge size="sm" variant="light" color="pink">hallucinated</Badge>}
        {(cell.flags || []).map((f, i) => <Badge key={i} size="sm" variant="light" color="yellow">{f}</Badge>)}
        {cell.n_tool_calls != null && <Text size="xs" c="dimmed">{cell.n_tool_calls} tool calls</Text>}
        {cell.runtime_secs != null && <Text size="xs" c="dimmed">{cell.runtime_secs}s</Text>}
      </Group>

      {cell.error
        ? <Code block c="red" style={pre}>{cell.error}</Code>
        : <Code block style={pre}>{cell.response}</Code>}

      {cell.tool_calls_by_group && Object.keys(cell.tool_calls_by_group).length > 0 && (
        <Text size="xs" c="dimmed" ff="monospace" mt={6}>
          {Object.entries(cell.tool_calls_by_group).map(([g, n]) => `${g}:${n}`).join("  ")}
        </Text>
      )}

      {cell.hard_facts?.length > 0 && (
        <Box mt="sm">
          <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={4}>Hard facts</Text>
          <FactChips facts={cell.hard_facts} />
        </Box>
      )}

      {cell.claims?.length > 0 && (
        <Box mt="sm">
          <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={4}>Judge claims</Text>
          <Stack gap={6}>
            {cell.claims.map((c, i) => (
              <Group key={i} gap={8} align="baseline" wrap="nowrap">
                <Badge size="sm" variant="light" color={claimColor(c.verdict)}>{c.verdict}</Badge>
                <Text size="sm" c="dimmed">{c.claim}</Text>
              </Group>
            ))}
            {(cell.hallucinations || []).map((h, i) => (
              <Group key={`h${i}`} gap={8} align="baseline" wrap="nowrap">
                <Badge size="sm" variant="light" color="pink">halluc</Badge>
                <Text size="sm" c="dimmed">{h.assertion || String(h)}</Text>
              </Group>
            ))}
          </Stack>
        </Box>
      )}

      {cell.has_transcript && (
        <Box mt="sm">
          <Group justify="space-between" mb={4}>
            <Text size="xs" tt="uppercase" fw={600} c="dimmed">Transcript</Text>
            <Button size="compact-xs" variant="subtle" onClick={loadTr}>load</Button>
          </Group>
          {tr && (
            <Stack gap={4}>
              {(tr.transcript || []).map((s, i) => (
                <Box key={i} pl="sm" style={{ borderLeft: "2px solid var(--mantine-color-dark-3)" }}>
                  <Text ff="monospace" size="xs" fw={600}>
                    #{s.step} {s.type === "tool" ? `${s.tool} ${JSON.stringify(s.args)}` : s.type}
                  </Text>
                  {s.result && <Code block style={{ ...pre, maxHeight: 180 }}>{s.result}</Code>}
                  {s.stdout && <Code block style={{ ...pre, maxHeight: 180 }}>{s.stdout}</Code>}
                </Box>
              ))}
            </Stack>
          )}
        </Box>
      )}
    </Paper>
  );
}
