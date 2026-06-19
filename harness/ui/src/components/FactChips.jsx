import { Group, Code } from "@mantine/core";

// Hard-fact verdicts as colored mono chips. `facts` = [{field, value, status?}],
// status one of matched / missing / not_gradeable. Shared by the gold facts and
// the per-run deterministic tier.
const COLOR = {
  matched: { color: "var(--mantine-color-teal-4)", border: "var(--mantine-color-teal-9)" },
  missing: { color: "var(--mantine-color-red-4)", border: "var(--mantine-color-red-9)" },
};

export function FactChips({ facts }) {
  if (!facts?.length) return null;
  return (
    <Group gap={6} mt={6}>
      {facts.map((f, i) => {
        const c = COLOR[f.status];
        return (
          <Code
            key={i}
            style={{
              fontSize: 11,
              color: c?.color,
              border: `1px solid ${c?.border || "var(--mantine-color-dark-4)"}`,
            }}
          >
            {f.field}: {f.value}{f.status ? ` — ${f.status}` : ""}
          </Code>
        );
      })}
    </Group>
  );
}
