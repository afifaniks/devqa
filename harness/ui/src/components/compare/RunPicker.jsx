import { Paper, Group, Text, Badge, SimpleGrid } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

// One selectable column per (run × judge). A run graded by several judges expands into
// one card per judge — selecting two judge-cards of the same run compares those gradings
// side by side. Column value is `run` or `run@judge-slug`; the latter pins a judge.
function columnsFor(r) {
  const gradings = r.gradings || [];
  if (gradings.length <= 1) {
    return [{ value: r.name, run: r.name, judge: gradings[0]?.judge_model || null }];
  }
  return gradings.map(gr => ({
    value: `${r.name}@${gr.slug}`,
    run: r.name,
    judge: gr.judge_model || gr.slug,
  }));
}

export function RunPicker({ runs, selected, onToggle }) {
  const cols = runs.flatMap(r =>
    columnsFor(r).map(c => ({ ...c, model: r.model, is_agent: r.is_agent, n_done: r.n_done })));

  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="xs">
      {cols.map(c => {
        const sel = selected.includes(c.value);
        return (
          <Paper
            key={c.value} withBorder p="sm" radius="md"
            onClick={() => onToggle(c.value)}
            style={{
              cursor: "pointer",
              borderColor: sel ? "var(--mantine-color-azure-5)" : undefined,
              background: sel ? "var(--mantine-color-azure-light)" : undefined,
            }}
          >
            <Group justify="space-between" wrap="nowrap" mb={4}>
              <Text ff="monospace" size="xs" fw={600} style={{ wordBreak: "break-all" }}>
                {c.run}
              </Text>
              {sel && <IconCheck size={15} color="var(--c-azure)" />}
            </Group>
            <Group gap={8}>
              <Text size="xs" c="dimmed">{c.model}</Text>
              {c.is_agent && <Badge size="xs" variant="light" color="violet">agent</Badge>}
              {c.judge
                ? <Badge size="xs" variant="light" color="teal">judge: {c.judge}</Badge>
                : <Text size="xs" c="dimmed">ungraded</Text>}
            </Group>
          </Paper>
        );
      })}
    </SimpleGrid>
  );
}
