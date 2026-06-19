import { Paper, Group, Text, Badge, SimpleGrid } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

// Multi-select run cards. Selecting ≥2 runs drives the side-by-side comparison.
export function RunPicker({ runs, selected, onToggle }) {
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="xs">
      {runs.map(r => {
        const sel = selected.includes(r.name);
        return (
          <Paper
            key={r.name} withBorder p="sm" radius="md"
            onClick={() => onToggle(r.name)}
            style={{
              cursor: "pointer",
              borderColor: sel ? "var(--mantine-color-azure-5)" : undefined,
              background: sel ? "var(--mantine-color-azure-light)" : undefined,
            }}
          >
            <Group justify="space-between" wrap="nowrap" mb={4}>
              <Text ff="monospace" size="xs" fw={600} style={{ wordBreak: "break-all" }}>
                {r.name}
              </Text>
              {sel && <IconCheck size={15} color="var(--mantine-color-azure-4)" />}
            </Group>
            <Group gap={8}>
              <Text size="xs" c="dimmed">{r.model}</Text>
              {r.is_agent && <Badge size="xs" variant="light" color="violet">agent</Badge>}
              <Text size="xs" c="dimmed">{r.n_done} done</Text>
              <Text size="xs" c="dimmed">{r.n_graded} graded</Text>
            </Group>
          </Paper>
        );
      })}
    </SimpleGrid>
  );
}
