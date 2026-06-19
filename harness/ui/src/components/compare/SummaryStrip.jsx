import { Paper, Text, Progress, Group, SimpleGrid } from "@mantine/core";
import { OUTCOME_ORDER } from "../../lib/outcomes.js";

const COLOR = {
  correct: "teal", partial: "yellow", incorrect: "red", error: "orange", ungraded: "dark.3",
};

// Per-run outcome distribution over the *filtered* question set — the signature
// data-viz: the verdict colors read at a glance, run against run.
export function SummaryStrip({ runs, tally }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="sm" mb="md">
      {runs.map(rn => {
        const t = tally[rn] || {};
        const total = OUTCOME_ORDER.reduce((a, o) => a + (t[o] || 0), 0) || 1;
        return (
          <Paper key={rn} withBorder p="sm" radius="md">
            <Text ff="monospace" size="xs" fw={600} mb={8} style={{ wordBreak: "break-all" }}>{rn}</Text>
            <Progress.Root size="lg" radius="sm">
              {OUTCOME_ORDER.map(o => t[o] > 0 && (
                <Progress.Section key={o} value={(100 * t[o]) / total} color={COLOR[o]}>
                  {t[o] / total > 0.12 ? t[o] : ""}
                </Progress.Section>
              ))}
            </Progress.Root>
            <Group gap="md" mt={8}>
              {OUTCOME_ORDER.map(o => t[o] > 0 && (
                <Text key={o} size="xs" c="dimmed">{o} {t[o]}</Text>
              ))}
            </Group>
          </Paper>
        );
      })}
    </SimpleGrid>
  );
}
