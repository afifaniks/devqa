import { Box, Group, Text, Badge, ThemeIcon, Loader } from "@mantine/core";
import { IconTool, IconCheck } from "@tabler/icons-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

// One colour per artifact group, matching the snapshot tool groups (RQ4).
const GROUP_COLOR = {
  code: "blue", commits: "grape", issues: "teal", prs: "orange", advisory: "red",
};

const slugOf = qid => String(qid || "").replaceAll("/", "__");
const argSummary = args => {
  if (!args || typeof args !== "object") return "";
  const v = Object.values(args).map(x => String(x)).filter(Boolean);
  return v.length ? v.join(" · ").slice(0, 80) : "";
};

// Live tool/answer timeline for the item currently in flight. Polls /api/live every
// ~1.5s, accumulating events incrementally (the `since` cursor), and renders each tool
// call + its result as it happens — the streaming agent (harness/stream_agent.py) appends
// these to <qid>.live.jsonl while the model works.
export function LiveTimeline({ runName, currentQid }) {
  const [events, setEvents] = useState([]);
  const [done, setDone] = useState(false);
  const cursor = useRef(0);
  const slug = slugOf(currentQid);

  // Reset when the in-flight item changes.
  useEffect(() => {
    cursor.current = 0;
    setEvents([]);
    setDone(false);
  }, [runName, slug]);

  useEffect(() => {
    if (!runName || !slug) return undefined;
    let alive = true;
    const tick = async () => {
      try {
        const r = await api.live(runName, slug, cursor.current);
        if (!alive) return;
        if (r.events?.length) {
          cursor.current = r.total;
          setEvents(prev => [...prev, ...r.events]);
        }
        setDone(r.done);
      } catch { /* item may not have started writing yet */ }
    };
    tick();
    const id = setInterval(tick, 1500);
    return () => { alive = false; clearInterval(id); };
  }, [runName, slug]);

  // Pair tool_call with its tool_result (by tool name, in order) for a tidy display.
  const calls = events.filter(e => e.t === "tool_call");
  const results = events.filter(e => e.t === "tool_result");
  const tokens = events.filter(e => e.t === "token").map(e => e.text).join("");
  const ended = events.find(e => e.t === "final" || e.t === "final_forced");

  if (!events.length) {
    return <Text size="xs" c="dimmed" mt="xs">waiting for the agent to start…</Text>;
  }

  return (
    <Box mt="xs">
      <Group gap={6} mb={6}>
        <Text size="xs" fw={600} c="dimmed">live trajectory</Text>
        <Badge size="xs" variant="light" color="gray">{calls.length} tool calls</Badge>
        {!done && <Loader size={11} color="teal" />}
      </Group>
      <Box style={{ maxHeight: 240, overflow: "auto",
                    borderLeft: "2px solid var(--mantine-color-dark-4)", paddingLeft: 8 }}>
        {calls.map((c, i) => {
          const res = results[i];           // results arrive in call order
          const color = GROUP_COLOR[c.group] || "gray";
          return (
            <Group key={i} gap={6} wrap="nowrap" align="center" mb={3}>
              <ThemeIcon size={16} radius="sm" variant="light"
                         color={res ? color : "gray"}>
                {res ? <IconCheck size={11} /> : <IconTool size={11} />}
              </ThemeIcon>
              <Badge size="xs" variant="light" color={color}
                     style={{ flex: "none" }}>{c.tool}</Badge>
              <Text size="xs" c="dimmed" ff="monospace" truncate title={argSummary(c.args)}>
                {argSummary(c.args)}
              </Text>
              <Text size="xs" c="dimmed" ff="monospace" ml="auto" style={{ flex: "none" }}>
                {res ? `${res.chars}b` : "…"}
              </Text>
            </Group>
          );
        })}
        {tokens && (
          <Text size="xs" mt={6} style={{ whiteSpace: "pre-wrap" }}>{tokens}</Text>
        )}
        {ended && (
          <Text size="xs" c="teal" mt={6} fw={600}>
            ✓ {ended.t === "final_forced" ? "answer (forced, out of budget)" : "answer"} · {ended.chars}b
          </Text>
        )}
      </Box>
    </Box>
  );
}
