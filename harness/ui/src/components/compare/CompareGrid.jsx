import { Group, Badge, Text, Box, Code, Paper, SimpleGrid } from "@mantine/core";
import { IconChevronRight, IconChevronDown } from "@tabler/icons-react";
import { VERDICT_COLOR } from "../../theme.js";
import { outcomeOf } from "../../lib/outcomes.js";
import { ktLabel } from "../../lib/benchmark.js";
import { FactChips } from "../FactChips.jsx";
import { DetailColumn } from "./DetailColumn.jsx";

const pre = { whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12, maxHeight: 320, overflow: "auto" };

function Cell({ cell }) {
  if (!cell) return <Text className="cmp-cell" c="dimmed" fs="italic" size="xs">—</Text>;
  const o = outcomeOf(cell);
  return (
    <Box className="cmp-cell">
      <Group gap={6}>
        <Badge size="sm" variant="light" color={VERDICT_COLOR[o] || "gray"}>{o}</Badge>
        {cell.hallucinated && <Badge size="sm" variant="light" color="pink">☄</Badge>}
        {cell.n_tool_calls != null && <Text size="xs" c="dimmed">{cell.n_tool_calls} tools</Text>}
        {cell.runtime_secs != null && <Text size="xs" c="dimmed">{cell.runtime_secs}s</Text>}
      </Group>
      <Text
        className={"clamp" + (cell.error ? "" : "")}
        c={cell.error ? "red.4" : "dimmed"} size="xs" mt={6}
        style={{ "--lines": 5 }}
      >
        {cell.error || cell.response}
      </Text>
    </Box>
  );
}

function Row({ row, runs, cols, open, onToggle }) {
  return (
    <>
      <div className="cmp-row" style={{ gridTemplateColumns: cols }}>
        <Box className="cmp-cell cmp-qcell" onClick={onToggle}>
          <Group gap={6} wrap="nowrap" align="center">
            {open ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
            <Text ff="monospace" size="xs" c="var(--c-azure)" style={{ wordBreak: "break-all" }}>{row.qid}</Text>
          </Group>
          <Group gap={8} mt={4}>
            {row.knowledge_type && <Text size="xs" c="dimmed">{ktLabel(row.knowledge_type)}</Text>}
            {row.repo && <Text size="xs" c="dimmed">{row.repo}</Text>}
            {!row.in_corpus && <Text size="xs" c="yellow.5">not in corpus</Text>}
          </Group>
          <Text className="clamp" c="dimmed" size="xs" mt={6} style={{ "--lines": 3 }}>
            {row.question || row.title || ""}
          </Text>
        </Box>
        {runs.map(rn => <Cell key={rn} cell={row.cells[rn]} />)}
      </div>

      {open && (
        <div className="cmp-row">
          <Box className="cmp-detail" p="md">
            <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default)" mb="sm">
              <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={6}>Question</Text>
              <Code block style={pre}>{row.question || "(not in corpus)"}</Code>
            </Paper>
            {row.gold_answer && (
              <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default)" mb="sm">
                <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={6}>Gold answer (maintainer)</Text>
                <Code block style={pre}>{row.gold_answer}</Code>
                <FactChips facts={row.hard_facts} />
                {row.grounding_sources?.length > 0 && (
                  <Text size="xs" c="dimmed" ff="monospace" mt={6}>
                    based on: {row.grounding_sources.join(", ")}
                  </Text>
                )}
              </Paper>
            )}
            <SimpleGrid cols={{ base: 1, md: Math.min(runs.length, 3) }} spacing="sm">
              {runs.map(rn => (
                <DetailColumn key={rn} runName={rn} cell={row.cells[rn]} qidSlug={row.qid_slug} />
              ))}
            </SimpleGrid>
          </Box>
        </div>
      )}
    </>
  );
}

// The side-by-side matrix: one row per question, one column per selected run.
export function CompareGrid({ rows, runMeta, selected, openQid, onToggleRow }) {
  const cols = `minmax(260px, 1.3fr) ${selected.map(() => "minmax(280px, 1fr)").join(" ")}`;
  return (
    <div className="cmp">
      <div className="cmp-grid">
        <div className="cmp-row cmp-head" style={{ gridTemplateColumns: cols }}>
          <Box className="cmp-cell"><Text size="xs" fw={600}>Question</Text></Box>
          {runMeta.map(r => (
            <Box className="cmp-cell" key={r.name}>
              <Text ff="monospace" size="xs" fw={600} style={{ wordBreak: "break-all" }}>{r.name}</Text>
              <Group gap={6} mt={2}>
                <Text size="xs" c="dimmed">{r.model}</Text>
                {r.is_agent && <Badge size="xs" variant="light" color="violet">agent</Badge>}
              </Group>
            </Box>
          ))}
        </div>
        {rows.map(row => (
          <Row
            key={row.qid} row={row} runs={selected} cols={cols}
            open={openQid === row.qid}
            onToggle={() => onToggleRow(openQid === row.qid ? null : row.qid)}
          />
        ))}
        {rows.length === 0 && (
          <Text c="dimmed" ta="center" py="xl">No questions match the filters.</Text>
        )}
      </div>
    </div>
  );
}
