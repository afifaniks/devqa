import { Stack, Group, Badge, Text, Box } from "@mantine/core";
import { RUBRIC_COLOR, RUBRIC_LABEL } from "../lib/outcomes.js";

// Per-criterion rubric grading for one response: each criterion shows met / partial /
// not-met (or n/a when gated out by knowable_at_report), its axis, and the response span
// the judge relied on. A small score summary leads. Used by the Monitor + Compare views.
//
// Falls back to nothing when a run was graded by the legacy claim-based grader (the
// caller renders that path instead).
export function RubricGrades({ grades, scores, hallucinations, compact = false }) {
  if (!grades?.length) return null;
  const fs = compact ? "sm" : "sm";
  return (
    <Stack gap={compact ? 6 : 8}>
      {scores && (
        <Group gap="md" wrap="wrap">
          <ScorePill label="correctness" value={scores.correctness} n={scores.n_correctness} color="teal" />
          <ScorePill label="completeness" value={scores.completeness} n={scores.n_completeness} color="indigo" />
        </Group>
      )}

      {grades.map(g => (
        <Group key={g.index} gap={8} align="flex-start" wrap="nowrap">
          <Badge size="sm" variant="light" color={RUBRIC_COLOR[g.verdict] || "gray"}
                 style={{ flex: "none", minWidth: 64 }}>
            {RUBRIC_LABEL[g.verdict] || g.verdict}
          </Badge>
          <Box style={{ flex: 1, minWidth: 0 }}>
            <Group gap={6} wrap="nowrap" align="baseline">
              {g.axis && (
                <Text size="10px" tt="uppercase" fw={600} c="dimmed" style={{ flex: "none" }}>
                  {g.axis === "correctness" ? "corr" : "compl"}
                </Text>
              )}
              <Text size={fs}>{g.text}</Text>
            </Group>
            {g.evidence && (
              <Text size="xs" c="dimmed" ff="monospace" mt={2}
                    style={{ borderLeft: "2px solid var(--mantine-color-default-border)", paddingLeft: 6 }}>
                “{g.evidence}”
              </Text>
            )}
          </Box>
        </Group>
      ))}

      {(hallucinations || []).map((h, i) => (
        <Group key={`h${i}`} gap={8} align="flex-start" wrap="nowrap">
          <Badge size="sm" variant="light" color="orange" style={{ flex: "none", minWidth: 64 }}>halluc</Badge>
          <Text size={fs} c="dimmed">{h.assertion || String(h)}</Text>
        </Group>
      ))}
    </Stack>
  );
}

function ScorePill({ label, value, n, color }) {
  return (
    <Group gap={5} wrap="nowrap">
      <Text size="10px" tt="uppercase" fw={600} c="dimmed">{label}</Text>
      <Badge size="sm" variant="light" color={n ? color : "gray"}>
        {value == null ? "—" : `${Math.round(value * 100)}%`}
        <Text span size="9px" c="dimmed" ml={4}>{n ?? 0}</Text>
      </Badge>
    </Group>
  );
}
