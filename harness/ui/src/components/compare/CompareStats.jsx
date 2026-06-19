import { useMemo } from "react";
import {
  Paper, SimpleGrid, Group, Stack, Text, RingProgress, Badge, Box, Alert,
} from "@mantine/core";
import { BarChart } from "@mantine/charts";
import { IconChartBar } from "@tabler/icons-react";
import { computeStats, knowledgeTypes, toolGroups, pct1 } from "../../lib/stats.js";
import { SectionLabel } from "../SectionLabel.jsx";

const GROUP_COLOR = {
  code: "azure.5", commits: "violet.5", issues: "teal.5",
  prs: "orange.5", advisory: "pink.5",
};
const fmtPct = v => `${v}%`;

function Metric({ label, value, dim }) {
  return (
    <Group justify="space-between" gap="xs">
      <Text size="xs" c="dimmed">{label}</Text>
      <Text size="xs" ff="monospace" c={dim ? "dimmed" : "bright"} fw={600}>{value}</Text>
    </Group>
  );
}

// One run's headline metrics: a composition ring (correct/partial/incorrect) with the
// partial-credit score in the center, plus the numbers that don't fit a chart.
function StatCard({ p }) {
  const ring = p.graded
    ? [
        { value: pct1(p.correct / p.graded), color: "teal" },
        { value: pct1(p.partial / p.graded), color: "yellow" },
        { value: pct1(p.incorrect / p.graded), color: "red" },
      ]
    : [{ value: 100, color: "dark.4" }];

  return (
    <Paper withBorder p="md" radius="md">
      <Group gap={6} mb="sm" wrap="nowrap">
        <Badge color={p.color.split(".")[0]} variant="filled" size="sm">{p.alias}</Badge>
        <Text ff="monospace" size="xs" fw={600} truncate>{p.name}</Text>
      </Group>
      <Group wrap="nowrap" align="center" gap="md">
        <RingProgress
          size={96} thickness={9} roundCaps sections={ring}
          label={
            <Stack gap={0} align="center">
              <Text ta="center" fw={700} size="md" lh={1}>
                {p.graded ? `${pct1(p.score)}%` : "—"}
              </Text>
              <Text ta="center" size="9px" c="dimmed" tt="uppercase">score</Text>
            </Stack>
          }
        />
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Metric label="correct" value={`${p.correct}/${p.graded || 0}`} />
          <Metric label="partial" value={p.partial} />
          <Metric label="hallucination" value={p.graded ? fmtPct(pct1(p.hallucRate)) : "—"} />
          <Metric
            label="hard facts"
            value={p.factsGradeable ? `${p.factsMatched}/${p.factsGradeable}` : "—"}
            dim={!p.factsGradeable}
          />
          <Metric
            label="avg tool calls"
            value={p.avgTools != null ? p.avgTools.toFixed(1) : "—"}
            dim={p.avgTools == null}
          />
        </Stack>
      </Group>
    </Paper>
  );
}

function ChartCard({ title, children }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb="md">{title}</Text>
      {children}
    </Paper>
  );
}

// Comparative analytics over the filtered question set: per-run cards + charts.
export function CompareStats({ rows, runs }) {
  const per = useMemo(() => computeStats(rows, runs), [rows, runs]);
  const ordered = runs.map(rn => per[rn]);
  const series = ordered.map(p => ({ name: p.alias, color: p.color }));

  const totalGraded = ordered.reduce((a, p) => a + p.graded, 0);

  // accuracy (partial-credit score %) by knowledge type
  const kts = knowledgeTypes(rows);
  const ktData = kts.map(kt => {
    const row = { kt };
    ordered.forEach(p => {
      const k = p.byKT[kt];
      row[p.alias] = k && k.graded ? pct1((k.correct + 0.5 * k.partial) / k.graded) : 0;
    });
    return row;
  });

  // hard-fact match rate %, only runs that had gradeable facts
  const factData = ordered
    .filter(p => p.factsGradeable > 0)
    .map(p => ({ run: p.alias, match: pct1(p.factMatchRate) }));

  // tool calls by artifact group (agent runs)
  const groups = toolGroups(per);
  const toolData = ordered
    .filter(p => Object.keys(p.toolByGroup).length)
    .map(p => {
      const row = { run: p.alias };
      groups.forEach(g => { row[g] = p.toolByGroup[g] || 0; });
      return row;
    });

  return (
    <>
      <SectionLabel>Statistics</SectionLabel>

      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="sm" mb="md">
        {ordered.map(p => <StatCard key={p.name} p={p} />)}
      </SimpleGrid>

      {totalGraded === 0 ? (
        <Alert variant="light" color="gray" icon={<IconChartBar size={16} />} mb="md">
          These runs aren’t graded yet — grade them (Monitor tab → “grade after”, or
          <Text span ff="monospace"> python -m harness grade</Text>) to see accuracy charts.
        </Alert>
      ) : (
        <SimpleGrid cols={{ base: 1, md: factData.length ? 2 : 1 }} spacing="sm" mb="md">
          <ChartCard title="Accuracy by knowledge type (partial-credit score)">
            <BarChart
              h={260} data={ktData} dataKey="kt" series={series}
              valueFormatter={fmtPct} yAxisProps={{ domain: [0, 100] }}
              withLegend tickLine="y"
            />
          </ChartCard>
          {factData.length > 0 && (
            <ChartCard title="Hard-fact match rate">
              <BarChart
                h={260} data={factData} dataKey="run"
                series={[{ name: "match", label: "matched %", color: "azure.5" }]}
                valueFormatter={fmtPct} yAxisProps={{ domain: [0, 100] }}
                tickLine="y"
              />
            </ChartCard>
          )}
        </SimpleGrid>
      )}

      {toolData.length > 0 && (
        <ChartCard title="Tool calls by artifact group (agent runs)">
          <BarChart
            h={240} data={toolData} dataKey="run" type="stacked"
            series={groups.map((g, i) => ({
              name: g,
              color: GROUP_COLOR[g] || ["azure.5", "violet.5", "teal.5", "orange.5", "pink.5"][i % 5],
            }))}
            withLegend tickLine="y"
          />
        </ChartCard>
      )}
    </>
  );
}
