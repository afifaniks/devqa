import { Group, Badge, Tooltip } from "@mantine/core";
import { hardFactChips } from "../../lib/benchmark.js";

// Render a hard_facts dict as compact verdict-colored chips. Verifiable identifiers
// (CVE/GHSA/CWE/OSV) read teal; fix references and versions stay quiet.
export function HardFactBadges({ hardFacts, gap = 6 }) {
  const chips = hardFactChips(hardFacts);
  if (!chips.length) return null;
  return (
    <Group gap={gap}>
      {chips.map((c, i) => (
        <Tooltip key={i} label={c.field} withArrow openDelay={300}>
          <Badge
            size="sm" variant={c.isId ? "light" : "outline"}
            color={c.isId ? "teal" : "gray"}
            styles={{ root: { textTransform: "none", fontFamily: "var(--mantine-font-family-monospace)" } }}
          >
            {c.label}: {c.value}
          </Badge>
        </Tooltip>
      ))}
    </Group>
  );
}
