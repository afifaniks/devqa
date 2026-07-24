import { Group, Text } from "@mantine/core";

// A quiet uppercase section heading with an optional mono count, used to
// structure the dense dashboard without shouting.
export function SectionLabel({ children, count, mt = "xl" }) {
  return (
    <Group gap={8} mt={mt} mb="sm" align="baseline">
      <Text size="xs" tt="uppercase" fw={600} c="dimmed" style={{ letterSpacing: ".11em" }}>
        {children}
      </Text>
      {count != null && <Text size="xs" c="dimmed" ff="monospace">{count}</Text>}
    </Group>
  );
}
