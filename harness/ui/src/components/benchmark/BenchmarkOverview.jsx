import { useMemo } from "react";
import { Paper, SimpleGrid, Group, Text, Stack, RingProgress } from "@mantine/core";
import { DonutChart, BarChart } from "@mantine/charts";

function Stat({ label, value, sub }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Text size="xs" tt="uppercase" fw={600} c="dimmed" style={{ letterSpacing: ".07em" }}>{label}</Text>
      <Text size="28px" fw={700} ff="monospace" lh={1.1} mt={6}>{value}</Text>
      {sub && <Text size="xs" c="dimmed" mt={4}>{sub}</Text>}
    </Paper>
  );
}

// A dataset "card": headline counts + how the QA pairs distribute across knowledge
// type and the artifacts maintainers drew on (the paper's RQ2).
export function BenchmarkOverview({ items, facets }) {
  const s = useMemo(() => {
    const grounded = items.filter(i => i.knowledge_type === "grounded").length;
    const parametric = items.filter(i => i.knowledge_type === "parametric").length;
    const withId = items.filter(i => i.has_hard_id).length;
    const artifactCounts = {};
    for (const it of items) for (const a of it.artifacts_needed || []) {
      artifactCounts[a] = (artifactCounts[a] || 0) + 1;
    }
    const artifactData = Object.entries(artifactCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([artifact, count]) => ({ artifact, count }));
    return { grounded, parametric, withId, artifactData };
  }, [items]);

  const total = items.length || 1;
  const ktDonut = [
    { name: "grounded", value: s.grounded, color: "teal.5" },
    { name: "parametric", value: s.parametric, color: "violet.5" },
  ];

  return (
    <>
      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="sm" mb="md">
        <Stat label="QA pairs" value={items.length} />
        <Stat label="Repositories" value={facets.repos?.length ?? "—"} />
        <Stat label="Grounded / parametric" value={`${s.grounded} / ${s.parametric}`}
              sub={`${Math.round((100 * s.grounded) / total)}% grounded`} />
        <Stat label="With verifiable ID" value={s.withId}
              sub={`${Math.round((100 * s.withId) / total)}% have CVE/GHSA/CWE/OSV`} />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm" mb="md">
        <Paper withBorder p="md" radius="md">
          <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb="md">Knowledge type</Text>
          <Group justify="center">
            <DonutChart
              data={ktDonut} size={150} thickness={26} withTooltip
              chartLabel={`${items.length}`}
            />
            <Stack gap={6}>
              {ktDonut.map(d => (
                <Group key={d.name} gap={8}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: `var(--mantine-color-${d.color.replace(".", "-")})` }} />
                  <Text size="sm">{d.name}</Text>
                  <Text size="sm" c="dimmed" ff="monospace">{d.value}</Text>
                </Group>
              ))}
            </Stack>
          </Group>
        </Paper>

        <Paper withBorder p="md" radius="md">
          <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb="md">Artifacts needed to answer</Text>
          <BarChart
            h={260} data={s.artifactData} dataKey="artifact" orientation="horizontal"
            series={[{ name: "count", color: "azure.5" }]}
            yAxisProps={{ width: 130 }} barProps={{ radius: 3 }} gridAxis="none"
          />
        </Paper>
      </SimpleGrid>
    </>
  );
}
