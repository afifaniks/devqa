import { useMemo, useState } from "react";
import {
  Paper, Group, Stack, Text, Badge, Tooltip, Box, SegmentedControl, ScrollArea,
} from "@mantine/core";
import {
  IconCheck, IconX, IconMinus, IconAlertTriangle, IconPointFilled,
} from "@tabler/icons-react";
import { RUN_PALETTE } from "../../lib/stats.js";
import { outcomeOf } from "../../lib/outcomes.js";
import { ktLabel } from "../../lib/benchmark.js";
import { SectionLabel } from "../SectionLabel.jsx";

const aliasOf = i => `R${i + 1}`;
const colorOf = i => RUN_PALETTE[i % RUN_PALETTE.length].split(".")[0];

// One run's verdict on one question → a color-coded mark.
const MARKS = {
  correct:   { Icon: IconCheck,         color: "teal.5",   title: "correct" },
  partial:   { Icon: IconMinus,         color: "yellow.5", title: "partial" },
  incorrect: { Icon: IconX,             color: "red.5",    title: "incorrect" },
  error:     { Icon: IconAlertTriangle, color: "orange.5", title: "error" },
  ungraded:  { Icon: IconPointFilled,   color: "gray.6",   title: "ungraded / missing" },
};

function Mark({ cell }) {
  const o = cell ? outcomeOf(cell) : null;
  const m = MARKS[o] || MARKS.ungraded;
  const M = m.Icon;
  const extra = cell?.hallucinated ? " · hallucinated" : "";
  return (
    <Tooltip label={m.title + extra} withArrow openDelay={150}>
      <Box style={{ display: "flex", justifyContent: "center" }}>
        <M size={18} stroke={2.4} color={`var(--mantine-color-${m.color.replace(".", "-")})`} />
      </Box>
    </Tooltip>
  );
}

// Compact correctness matrix: one row per question, one column per run, each cell a
// color-coded ✓ / ✗ / partial / – mark. A scannable companion to the detailed grid.
// `runs` are the run names in selection order; `rows` the currently-filtered rows.
export function SolvedMatrix({ rows, runs }) {
  const [solved, setSolved] = useState("correct"); // what counts as a "win" for sorting
  const [sortByWins, setSortByWins] = useState(false);

  const isWin = (cell) => {
    if (!cell || !cell.graded) return false;
    const o = outcomeOf(cell);
    return solved === "partial" ? o === "correct" || o === "partial" : o === "correct";
  };

  // Per-run win counts for the header, over graded cells.
  const tally = useMemo(() => runs.map((rn) => {
    let wins = 0, graded = 0;
    for (const row of rows) {
      const c = row.cells[rn];
      if (c && c.graded) { graded++; if (isWin(c)) wins++; }
    }
    return { wins, graded };
  }), [rows, runs, solved]);

  const ordered = useMemo(() => {
    if (!sortByWins) return rows;
    // Most-solved questions first (by how many runs won), then by qid for stability.
    const score = (row) => runs.reduce((a, rn) => a + (isWin(row.cells[rn]) ? 1 : 0), 0);
    return [...rows].sort((a, b) => score(b) - score(a) || (a.qid < b.qid ? -1 : 1));
  }, [rows, runs, sortByWins, solved]);

  if (runs.length < 2) return null;
  // Question column flexes; each run column is a fixed narrow track.
  const cols = `minmax(220px, 1fr) ${runs.map(() => "44px").join(" ")}`;
  const cell = { padding: "4px 8px", display: "flex", alignItems: "center" };

  return (
    <>
      <SectionLabel count={`${rows.length} question${rows.length === 1 ? "" : "s"}`}>
        Correctness matrix
      </SectionLabel>
      <Paper withBorder radius="md" mb="md" style={{ overflow: "hidden" }}>
        <Group justify="space-between" p="sm" wrap="wrap">
          <Group gap={6}>
            {Object.entries(MARKS).map(([k, m]) => {
              const M = m.Icon;
              return (
                <Group key={k} gap={3}>
                  <M size={14} stroke={2.4}
                     color={`var(--mantine-color-${m.color.replace(".", "-")})`} />
                  <Text size="xs" c="dimmed">{m.title.split(" ")[0]}</Text>
                </Group>
              );
            })}
          </Group>
          <Group gap="xs">
            <SegmentedControl
              size="xs" value={solved} onChange={setSolved}
              data={[{ label: "✓ = correct", value: "correct" },
                     { label: "✓ = + partial", value: "partial" }]}
            />
            <SegmentedControl
              size="xs" value={sortByWins ? "wins" : "order"}
              onChange={v => setSortByWins(v === "wins")}
              data={[{ label: "filtered order", value: "order" },
                     { label: "most-solved first", value: "wins" }]}
            />
          </Group>
        </Group>

        <ScrollArea.Autosize mah={560} type="auto">
          <div style={{ minWidth: 220 + runs.length * 44 }}>
            {/* header */}
            <Box style={{ display: "grid", gridTemplateColumns: cols, position: "sticky",
                          top: 0, zIndex: 1, background: "var(--mantine-color-body)",
                          borderBottom: "1px solid var(--mantine-color-default-border)" }}>
              <Box style={cell}><Text size="xs" fw={600}>Question</Text></Box>
              {runs.map((rn, i) => (
                <Tooltip key={rn} label={`${rn} — ${tally[i].wins}/${tally[i].graded} solved`}
                         withArrow>
                  <Box style={{ ...cell, justifyContent: "center", flexDirection: "column",
                                gap: 0 }}>
                    <Badge size="xs" variant="light" color={colorOf(i)}>{aliasOf(i)}</Badge>
                    <Text size="9px" c="dimmed" ff="monospace">{tally[i].wins}</Text>
                  </Box>
                </Tooltip>
              ))}
            </Box>
            {/* rows */}
            {ordered.map((row, ri) => (
              <Box key={row.qid}
                   style={{ display: "grid", gridTemplateColumns: cols,
                            background: ri % 2 ? "var(--mantine-color-default-hover)" : "transparent",
                            borderBottom: "1px solid var(--mantine-color-default-border)" }}>
                <Box style={cell}>
                  <Stack gap={0} style={{ minWidth: 0 }}>
                    <Text ff="monospace" size="xs" c="var(--c-azure)" truncate>{row.qid}</Text>
                    <Group gap={6} wrap="nowrap">
                      {row.knowledge_type && (
                        <Text size="9px" c="dimmed">{ktLabel(row.knowledge_type)}</Text>)}
                      {row.repo && <Text size="9px" c="dimmed" truncate>{row.repo}</Text>}
                    </Group>
                  </Stack>
                </Box>
                {runs.map(rn => (
                  <Box key={rn} style={{ ...cell, justifyContent: "center" }}>
                    <Mark cell={row.cells[rn]} />
                  </Box>
                ))}
              </Box>
            ))}
            {ordered.length === 0 && (
              <Text c="dimmed" ta="center" py="xl">No questions match the filters.</Text>
            )}
          </div>
        </ScrollArea.Autosize>
      </Paper>
    </>
  );
}
