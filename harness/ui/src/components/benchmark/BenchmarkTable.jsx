import { Table, Badge, Text, Group, Box } from "@mantine/core";
import { IconChevronRight } from "@tabler/icons-react";
import { KT_COLOR, ktLabel, ROLE_COLOR } from "../../lib/benchmark.js";
import { HardFactBadges } from "./HardFactBadges.jsx";

// HuggingFace-style dense listing of QA pairs; each row opens the detail view.
export function BenchmarkTable({ items, onOpen }) {
  return (
    <Box className="cmp" style={{ maxHeight: "calc(100vh - 250px)" }}>
      <Table stickyHeader highlightOnHover verticalSpacing="sm" horizontalSpacing="md"
             style={{ minWidth: 860 }}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Repository</Table.Th>
            <Table.Th>Question</Table.Th>
            <Table.Th w={110}>Type</Table.Th>
            <Table.Th w={120}>Answerer</Table.Th>
            <Table.Th w={90}>Rubric</Table.Th>
            <Table.Th>Hard facts</Table.Th>
            <Table.Th w={28} />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {items.map(it => (
            <Table.Tr key={it.qid} style={{ cursor: "pointer" }} onClick={() => onOpen(it.slug)}>
              <Table.Td>
                <Text ff="monospace" size="xs" fw={600}>{it.repo}</Text>
                <Text ff="monospace" size="xs" c="dimmed">#{it.number}</Text>
              </Table.Td>
              <Table.Td maw={460}>
                <Text size="sm" fw={500} lineClamp={1}>{it.title || it.qid}</Text>
                {it.security_topic && (
                  <Text size="xs" c="dimmed" lineClamp={1}>{it.security_topic}</Text>
                )}
              </Table.Td>
              <Table.Td>
                <Badge size="sm" variant="light" color={KT_COLOR[it.knowledge_type] || "gray"}>
                  {ktLabel(it.knowledge_type)}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Badge size="sm" variant="dot" color={ROLE_COLOR[it.answerer_role] || "gray"}>
                  {it.answerer_role}
                </Badge>
              </Table.Td>
              <Table.Td>
                {it.n_rubric
                  ? <Badge size="sm" variant="light" color="gray">{it.n_rubric} crit</Badge>
                  : <Text size="xs" c="dimmed">—</Text>}
              </Table.Td>
              <Table.Td maw={260}>
                {Object.keys(it.hard_facts || {}).length
                  ? <HardFactBadges hardFacts={it.hard_facts} />
                  : <Text size="xs" c="dimmed">—</Text>}
              </Table.Td>
              <Table.Td>
                <Group justify="flex-end"><IconChevronRight size={15} color="var(--mantine-color-dimmed)" /></Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Box>
  );
}
