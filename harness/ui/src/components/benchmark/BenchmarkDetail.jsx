import { useEffect, useState } from "react";
import {
  Button, Group, Stack, Text, Badge, Paper, Grid, Anchor, Box, Divider, Loader,
} from "@mantine/core";
import {
  IconArrowLeft, IconExternalLink, IconMessage2, IconShieldCheck, IconUser,
  IconListCheck, IconClock, IconClockOff,
} from "@tabler/icons-react";
import { api } from "../../api.js";
import { asItems, sourceInfo, KT_COLOR, ktLabel, ROLE_COLOR } from "../../lib/benchmark.js";
import { Markdown } from "../Markdown.jsx";
import { HardFactBadges } from "./HardFactBadges.jsx";

function Panel({ title, icon, right, children }) {
  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" mb="sm">
        <Group gap={8}>{icon}<Text fw={600} size="sm">{title}</Text></Group>
        {right}
      </Group>
      {children}
    </Paper>
  );
}

function Def({ label, children }) {
  if (children == null || children === "" ) return null;
  return (
    <Box>
      <Text size="xs" tt="uppercase" fw={600} c="dimmed" style={{ letterSpacing: ".06em" }}>{label}</Text>
      <Box mt={3}>{children}</Box>
    </Box>
  );
}

function Comment({ c, role }) {
  const color = role === "question" ? "azure" : role === "answer" ? "teal" : null;
  return (
    <Paper
      withBorder p="sm" radius="md"
      style={color ? { borderColor: `var(--mantine-color-${color}-7)` } : undefined}
    >
      <Group gap={8} mb={6} wrap="wrap">
        <Text ff="monospace" size="xs" c="dimmed">{c.id}</Text>
        <Group gap={5}><IconUser size={13} /><Text size="xs" fw={600}>{c.author}</Text></Group>
        {c.role && <Badge size="xs" variant="light" color="gray">{c.role}</Badge>}
        {color && <Badge size="xs" variant="filled" color={color}>{role}</Badge>}
        <Text size="xs" c="dimmed" ml="auto">{c.timestamp}</Text>
      </Group>
      <Markdown fontSize={13}>{c.body}</Markdown>
    </Paper>
  );
}

const AXIS_COLOR = { correctness: "orange", completeness: "indigo" };

function Criterion({ c, n }) {
  const Knowable = c.knowable_at_report ? IconClock : IconClockOff;
  const src = sourceInfo(c.source_loc);
  return (
    <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-body)">
      <Group gap={10} mb={6} wrap="nowrap" align="flex-start">
        <Box
          style={{
            flex: "none", width: 22, height: 22, borderRadius: "50%",
            display: "grid", placeItems: "center",
            background: "var(--mantine-color-green-light)",
            color: "var(--c-green)", fontSize: 12, fontWeight: 700,
          }}
        >
          {n}
        </Box>
        <Text size="sm" style={{ flex: 1 }}>{c.text}</Text>
        {c.axis && (
          <Badge size="xs" variant="light" color={AXIS_COLOR[c.axis] || "gray"}>{c.axis}</Badge>
        )}
      </Group>
      {/* Show the quoted span only when it's external evidence (a fix diff / advisory /
          verified fact). Answer-side spans just repeat the gold answer shown above. */}
      {src.external && c.source_quote && (
        <Box pl={30}>
          <Text size="xs" ff="monospace" c="dimmed"
                style={{ borderLeft: "2px solid var(--mantine-color-grape-7)", paddingLeft: 8, whiteSpace: "pre-wrap" }}>
            {c.source_quote}
          </Text>
        </Box>
      )}
      <Group gap={10} mt={6} pl={30}>
        <Badge size="xs" variant={src.external ? "light" : "outline"}
               color={src.external ? "grape" : "gray"}
               styles={{ root: { textTransform: "none" } }}>
          {src.external ? "evidence" : "from"}: {src.label}
        </Badge>
        <Group gap={3}>
          <Knowable size={12} color="var(--mantine-color-dimmed)" />
          <Text size="xs" c="dimmed">
            {c.knowable_at_report ? "knowable at report time" : "post-report"}
          </Text>
        </Group>
      </Group>
    </Paper>
  );
}

function RubricPanel({ rubric, alternatives, note }) {
  alternatives = asItems(alternatives);   // tolerate string-or-list authoring
  if (!rubric?.length && !alternatives.length && !note) return null;
  return (
    <Paper
      withBorder p="md" radius="md"
      style={{
        borderLeft: "4px solid var(--c-green)",
        background: "var(--mantine-color-green-light)",
      }}
    >
      <Group justify="space-between" mb="sm">
        <Group gap={8}>
          <IconListCheck size={17} color="var(--c-green)" />
          <Text fw={700} size="sm" c="var(--c-green)">Grading rubric</Text>
        </Group>
        {rubric?.length ? <Badge size="xs" variant="light" color="green">{rubric.length} criteria</Badge> : null}
      </Group>
      <Stack gap="sm">
        {rubric.map((c, i) => <Criterion key={i} c={c} n={i + 1} />)}
        {alternatives?.length > 0 && (
          <Box>
            <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={4}>Acceptable alternatives</Text>
            <Stack gap={4}>
              {alternatives.map((a, i) => (
                <Text key={i} size="xs" c="dimmed">• {a}</Text>
              ))}
            </Stack>
          </Box>
        )}
        {note && (
          <Box>
            <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={4}>Reviewer note</Text>
            <Paper bg="var(--mantine-color-default)" p="xs" radius="sm"><Text size="xs" c="dimmed">{note}</Text></Paper>
          </Box>
        )}
      </Stack>
    </Paper>
  );
}

export function BenchmarkDetail({ slug, onBack }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let live = true;
    setD(null); setErr(null);
    api.benchmarkItem(slug).then(x => live && setD(x)).catch(e => live && setErr(String(e.message || e)));
    return () => { live = false; };
  }, [slug]);

  const back = (
    <Button variant="subtle" size="compact-sm" leftSection={<IconArrowLeft size={15} />} onClick={onBack}>
      Back to benchmark
    </Button>
  );

  if (err) return <Stack><Group>{back}</Group><Text c="var(--c-red)" ta="center" py="xl">{err}</Text></Stack>;
  if (!d) return <Stack><Group>{back}</Group><Group justify="center" py="xl"><Loader /></Group></Stack>;

  const sources = asItems(d.grounding_sources);
  const refs = asItems(d.answer_in_thread_refs);
  const leaks = asItems(d.leak_flags);
  const roleOf = id =>
    id === d.question_comment_id ? "question" : id === d.answer_comment_id ? "answer" : null;

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="wrap">
        {back}
        {d.url && (
          <Anchor href={d.url} target="_blank" size="sm">
            <Group gap={5}>view on GitHub <IconExternalLink size={14} /></Group>
          </Anchor>
        )}
      </Group>

      <Box>
        <Group gap={8} mb={4}>
          <Text ff="monospace" size="sm" c="var(--c-azure)">{d.qid}</Text>
          {d.state && <Badge size="sm" variant="light" color={d.state === "open" ? "teal" : "gray"}>{d.state}</Badge>}
          <Badge size="sm" variant="light" color={KT_COLOR[d.knowledge_type] || "gray"}>{ktLabel(d.knowledge_type)}</Badge>
        </Group>
        <Text size="xl" fw={700} lh={1.2}>{d.title}</Text>
        {d.security_topic && <Text c="dimmed" mt={4}>{d.security_topic}</Text>}
      </Box>

      <Grid gutter="md">
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Stack gap="md">
            <Panel
              title="Question" icon={<IconMessage2 size={16} />}
              right={d.question_author && <Text size="xs" c="dimmed">{d.question_author}</Text>}
            >
              <Markdown>{d.question}</Markdown>
            </Panel>

            <Panel
              title="Gold answer" icon={<IconShieldCheck size={16} color="var(--c-teal)" />}
              right={
                <Group gap={6}>
                  {d.answer_author && <Text size="xs" c="dimmed">{d.answer_author}</Text>}
                  {d.answerer_role && (
                    <Badge size="xs" variant="dot" color={ROLE_COLOR[d.answerer_role] || "gray"}>{d.answerer_role}</Badge>
                  )}
                </Group>
              }
            >
              <Markdown>{d.answer}</Markdown>
              {Object.keys(d.hard_facts || {}).length > 0 && (
                <>
                  <Divider my="sm" label="hard facts" labelPosition="left" />
                  <HardFactBadges hardFacts={d.hard_facts} />
                </>
              )}
              {sources.length > 0 && (
                <Box mt="sm">
                  <Text size="xs" tt="uppercase" fw={600} c="dimmed" mb={4}>Grounding sources</Text>
                  <Stack gap={2}>
                    {sources.map((s, i) => (
                      /^https?:\/\//.test(s)
                        ? <Anchor key={i} href={s} target="_blank" size="xs" style={{ wordBreak: "break-all" }}>{s}</Anchor>
                        : <Text key={i} size="xs" ff="monospace" c="dimmed">{s}</Text>
                    ))}
                  </Stack>
                </Box>
              )}
            </Panel>

            <RubricPanel rubric={d.rubric} alternatives={d.acceptable_alternatives} note={d.rubric_note} />

            <Panel title={`Thread`} icon={<IconMessage2 size={16} />}
                   right={<Text size="xs" c="dimmed">{(d.comments || []).length} comments</Text>}>
              <Stack gap="sm">
                {(d.comments || []).map(c => <Comment key={c.id} c={c} role={roleOf(c.id)} />)}
              </Stack>
            </Panel>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Paper withBorder p="md" radius="md" style={{ position: "sticky", top: 72 }}>
            <Stack gap="md">
              <Def label="Repository"><Text size="sm" ff="monospace">{d.repo} #{d.number}</Text></Def>
              <Def label="Summary"><Text size="sm" c="dimmed">{d.qa_summary}</Text></Def>
              <Def label="Artifacts needed">
                <Group gap={6}>
                  {(d.artifacts_needed || []).map(a => (
                    <Badge key={a} size="sm" variant="outline" color="gray"
                           styles={{ root: { textTransform: "none" } }}>{a}</Badge>
                  ))}
                </Group>
              </Def>
              {refs.length > 0 && (
                <Def label="Answer in thread refs">
                  <Text size="xs" ff="monospace" c="dimmed">{refs.join(", ")}</Text>
                </Def>
              )}
              <Def label="Reporter"><Text size="sm">{d.reporter}</Text></Def>
              <Def label="Opened"><Text size="sm" c="dimmed">{d.created_at}</Text></Def>
              {d.closed_at && <Def label="Closed"><Text size="sm" c="dimmed">{d.closed_at}</Text></Def>}
              {(d.labels || []).length > 0 && (
                <Def label="Labels">
                  <Group gap={5}>
                    {d.labels.map(l => <Badge key={l} size="xs" variant="light" color="gray" styles={{ root: { textTransform: "none" } }}>{l}</Badge>)}
                  </Group>
                </Def>
              )}
              {d.llm_confidence != null && (
                <Def label="LLM confidence"><Text size="sm" ff="monospace">{d.llm_confidence}</Text></Def>
              )}
              {d.human_note && (
                <Def label="Author note">
                  <Paper bg="var(--mantine-color-default)" p="xs" radius="sm"><Text size="xs" c="dimmed">{d.human_note}</Text></Paper>
                </Def>
              )}
              {leaks.length > 0 && (
                <Def label="Leak flags">
                  <Group gap={5}>{leaks.map((l, i) => <Badge key={i} size="xs" variant="light" color="yellow">{l}</Badge>)}</Group>
                </Def>
              )}
            </Stack>
          </Paper>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
