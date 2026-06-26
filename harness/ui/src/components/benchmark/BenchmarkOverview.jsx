import { Box, Divider, Grid, Group, Paper, Progress, Stack, Text } from "@mantine/core";
import { useMemo } from "react";

// One compact headline metric: big number + caption.
function Metric({ value, label }) {
  return (
    <Box>
      <Text size="22px" fw={700} ff="monospace" lh={1}>{value}</Text>
      <Text size="10px" tt="uppercase" fw={600} c="dimmed" mt={2} style={{ letterSpacing: ".06em" }}>{label}</Text>
    </Box>
  );
}

// One artifact row: name · proportional bar · count. A ranking list reads better
// than a rotated-label bar chart for a handful of categories.
function Bar({ label, count, max }) {
  return (
    <Group gap="sm" wrap="nowrap">
      <Text size="xs"  tt="uppercase" w={150} ta="right" style={{ flex: "none" }}>
        {label.replace(/_/g, " ")}
      </Text>
      <Box style={{ flex: 1 }}>
        <Progress value={(count / max) * 100} color="azure" size="md" radius="sm" />
      </Box>
      <Text size="xs" ff="monospace" c="dimmed" w={28} style={{ flex: "none" }}>{count}</Text>
    </Group>
  );
}

// Dataset overview: headline counts, knowledge-type split, and the artifacts
// maintainers drew on to answer (the paper's RQ2).
export function BenchmarkOverview({ items, facets }) {
  const s = useMemo(() => {
    const grounded = items.filter(i => i.knowledge_type === "grounded").length;
    const parametric = items.filter(i => i.knowledge_type === "parametric").length;
    const withId = items.filter(i => i.has_hard_id).length;
    const counts = {};
    for (const it of items) for (const a of it.artifacts_needed || []) {
      counts[a] = (counts[a] || 0) + 1;
    }
    const artifacts = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return { grounded, parametric, withId, artifacts };
  }, [items]);

  const total = items.length || 1;
  const maxArt = s.artifacts[0]?.[1] || 1;
  const pctG = Math.round((100 * s.grounded) / total);

  return (
    <Paper withBorder p="md" radius="md" mb="md">
      <Grid gutter="xl">
        {/* Left: headline numbers + knowledge-type split */}
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Group gap="xl" mb="lg">
            <Metric value={items.length} label="QA pairs" />
            <Metric value={facets.repos?.length ?? "—"} label="Repositories" />
            <Metric value={s.withId} label="With CVE/GHSA/CWE" />
          </Group>

          <Text size="10px" tt="uppercase" fw={600} c="dimmed" mb={6} style={{ letterSpacing: ".06em" }}>
            Knowledge type
          </Text>
          <Progress.Root size={20} radius="sm">
            <Progress.Section value={pctG} color="teal" />
            <Progress.Section value={100 - pctG} color="violet" />
          </Progress.Root>
          <Group justify="space-between" mt={6}>
            <Group gap={6}>
              <span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--mantine-color-teal-5)" }} />
              <Text size="xs">contextual <Text span c="dimmed" ff="monospace">{s.grounded} · {pctG}%</Text></Text>
            </Group>
            <Group gap={6}>
              <span style={{ width: 9, height: 9, borderRadius: 2, background: "var(--mantine-color-violet-5)" }} />
              <Text size="xs">parametric <Text span c="dimmed" ff="monospace">{s.parametric} · {100 - pctG}%</Text></Text>
            </Group>
          </Group>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 1 }} visibleFrom="md">
          <Divider orientation="vertical" h="100%" mx="auto" />
        </Grid.Col>

        {/* Right: artifact ranking */}
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Text size="10px" tt="uppercase" fw={600} c="dimmed" mb="sm" style={{ letterSpacing: ".06em" }}>
            Artifacts needed to answer
          </Text>
          <Stack gap={7}>
            {s.artifacts.map(([label, count]) => (
              <Bar key={label} label={label} count={count} max={maxArt} />
            ))}
          </Stack>
        </Grid.Col>
      </Grid>
    </Paper>
  );
}
