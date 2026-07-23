import { useState, useEffect, useMemo } from "react";
import {
  Paper, Group, Stack, Select, Autocomplete, NumberInput, Checkbox, Button,
  Chip, Text, Code, Alert, Collapse, ScrollArea, TextInput, Badge, Divider,
} from "@mantine/core";
import {
  IconPlayerPlay, IconCheck, IconAlertTriangle, IconChevronRight,
  IconChevronDown, IconSearch, IconListCheck,
} from "@tabler/icons-react";
import { api } from "../api.js";
import { EgressEditor } from "./EgressEditor.jsx";

const PROVIDER_LABEL = { openai: "OpenAI", anthropic: "Anthropic", ollama: "Ollama (local)" };
const PROVIDER_ORDER = ["openai", "anthropic", "ollama"];

// Turn a flat list of LiteLLM ids into Autocomplete grouped data, by provider prefix.
function groupByProvider(ids) {
  const groups = {};
  for (const id of ids) {
    const prov = id.includes("/") ? id.split("/")[0] : "other";
    (groups[prov] ||= []).push(id);
  }
  const keys = [...new Set([...PROVIDER_ORDER.filter(k => groups[k]), ...Object.keys(groups)])];
  return keys.map(k => ({ group: PROVIDER_LABEL[k] || k, items: groups[k] }));
}

// Run evaluation from the UI: builds a LaunchBody and POSTs /api/launch, which
// spawns the matching `python -m harness …` CLI as a logged subprocess. The
// echoed command keeps the run reproducible from the shell. The launched
// process then shows up live in <ProcessList/>.
export function Launcher({ options, onLaunched }) {
  const [system, setSystem] = useState("agent");
  const [model, setModel] = useState("openai/gpt-5.4-mini");
  const [groups, setGroups] = useState([]); // empty = full snapshot
  const [webSearch, setWebSearch] = useState(false); // live-internet tools (+web)
  const [limit, setLimit] = useState("");
  const [unapproved, setUnapproved] = useState(false);
  const [gradeAfter, setGradeAfter] = useState(true);
  const [judge, setJudge] = useState("openai/gpt-5.4");
  const [onlyIds, setOnlyIds] = useState([]);      // manually chosen subset ([] = whole benchmark)
  // Note: every launch creates its own timestamped run; resume a run from its card.
  const [instances, setInstances] = useState([]);
  const [paneOpen, setPaneOpen] = useState(false); // instance-picker pane
  const [filter, setFilter] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const systems = options.systems || [];
  const sys = systems.find(s => s.id === system) || {};
  const allGroups = options.groups || [];

  // Load all benchmark instances for the selectable pane.
  useEffect(() => {
    api.benchmark().then(b => setInstances(
      (b.items || []).map(it => ({
        qid: it.qid,
        slug: it.slug || it.qid,
        repo: it.repo || "",
        title: it.title || "",
        knowledge_type: it.knowledge_type || "",
        security_topic: it.security_topic || "",
      }))
    )).catch(() => setInstances([]));
  }, []);

  const selected = useMemo(() => new Set(onlyIds), [onlyIds]);
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return instances;
    return instances.filter(it =>
      `${it.slug} ${it.repo} ${it.title} ${it.security_topic} ${it.knowledge_type}`
        .toLowerCase().includes(q)
    );
  }, [instances, filter]);

  const toggleId = qid => setOnlyIds(prev =>
    prev.includes(qid) ? prev.filter(x => x !== qid) : [...prev, qid]);
  const selectFiltered = () =>
    setOnlyIds(prev => [...new Set([...prev, ...filtered.map(it => it.qid)])]);
  const clearIds = () => setOnlyIds([]);

  const launch = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.launch({
        system,
        model: sys.needs_model || model ? model || null : null,
        groups: sys.has_groups && groups.length ? groups : null,
        web_search: sys.has_web ? webSearch : false,
        limit: onlyIds.length ? null : (limit ? parseInt(limit, 10) : null),
        include_unapproved: unapproved,
        grade_after: gradeAfter,
        judge: gradeAfter ? judge : null,
        only_ids: onlyIds.length ? onlyIds : null,
      });
      setMsg({ ok: true, run: r.run_name, cmd: r.cmd });
      onLaunched?.();
    } catch (e) {
      setMsg({ ok: false, cmd: String(e.message || e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
    <Paper withBorder p="md" radius="md">
      <Group align="flex-end" gap="lg" wrap="wrap">
        <Select
          label="System under test"
          w={260}
          value={system}
          onChange={setSystem}
          data={systems.map(s => ({
            value: s.id,
            label: s.available ? s.label : `${s.label} (not installed)`,
            disabled: !s.available,
          }))}
        />

        <Autocomplete
          label={`Model${sys.needs_model ? "" : " (optional passthrough)"}`}
          w={260}
          value={model}
          onChange={setModel}
          data={groupByProvider(options.model_suggestions || [])}
          placeholder={sys.needs_model ? "provider/model, e.g. openai/gpt-5.4" : "agent default"}
          comboboxProps={{ shadow: "md" }}
        />

        <NumberInput
          label="Limit" w={110} min={1} value={limit}
          placeholder="all" onChange={setLimit} allowDecimal={false}
          disabled={onlyIds.length > 0}
        />

        {gradeAfter && (
          <Autocomplete
            label="Judge" w={220} value={judge} onChange={setJudge}
            data={groupByProvider(options.judge_suggestions || [])}
            placeholder="provider/model"
            comboboxProps={{ shadow: "md" }}
          />
        )}

        <Button
          leftSection={<IconPlayerPlay size={16} />}
          loading={busy}
          disabled={sys.needs_model && !model}
          onClick={launch}
        >
          Launch run
        </Button>
      </Group>

      {/* Instance picker: expandable pane over the whole benchmark. Empty = run all. */}
      <Stack gap={6} mt="md">
        <Group gap="xs">
          <Button
            variant="subtle" size="xs" px={6}
            leftSection={paneOpen ? <IconChevronDown size={15} /> : <IconChevronRight size={15} />}
            onClick={() => setPaneOpen(o => !o)}
          >
            Instances
          </Button>
          {onlyIds.length ? (
            <>
              <Badge variant="light" color="blue" size="sm">
                {onlyIds.length} selected of {instances.length}
              </Badge>
              <Button variant="subtle" size="xs" color="gray" onClick={clearIds}>
                run whole benchmark
              </Button>
            </>
          ) : (
            <Text size="xs" c="dimmed">
              whole benchmark ({instances.length || "…"} items) — expand to pick a subset
            </Text>
          )}
        </Group>

        <Collapse in={paneOpen}>
          <Paper withBorder p="sm" radius="sm">
            <Group gap="sm" mb="xs">
              <TextInput
                placeholder="filter by repo, title, topic, slug…"
                value={filter}
                onChange={e => setFilter(e.currentTarget.value)}
                leftSection={<IconSearch size={14} />}
                w={320}
                size="xs"
              />
              <Button
                size="xs" variant="default"
                leftSection={<IconListCheck size={14} />}
                onClick={selectFiltered}
                disabled={!filtered.length}
              >
                select {filter.trim() ? `${filtered.length} shown` : "all"}
              </Button>
              <Button size="xs" variant="subtle" color="gray" onClick={clearIds} disabled={!onlyIds.length}>
                clear
              </Button>
              <Text size="xs" c="dimmed" ml="auto">
                {filtered.length} shown · {onlyIds.length} selected
              </Text>
            </Group>
            <Divider />
            <ScrollArea h={320} mt="xs" type="auto">
              <Stack gap={2}>
                {filtered.map(it => (
                  <Checkbox
                    key={it.qid}
                    checked={selected.has(it.qid)}
                    onChange={() => toggleId(it.qid)}
                    size="xs"
                    styles={{ label: { paddingLeft: 8 } }}
                    label={
                      <Group gap={6} wrap="nowrap">
                        <Code style={{ fontSize: 10 }}>{it.slug}</Code>
                        {it.knowledge_type && (
                          <Badge
                            size="xs" variant="light"
                            color={it.knowledge_type === "grounded" ? "grape" : "teal"}
                          >
                            {it.knowledge_type}
                          </Badge>
                        )}
                        <Text size="xs" lineClamp={1}>
                          {it.title || it.security_topic}
                        </Text>
                      </Group>
                    }
                  />
                ))}
                {!filtered.length && (
                  <Text size="xs" c="dimmed" ta="center" py="md">no match</Text>
                )}
              </Stack>
            </ScrollArea>
          </Paper>
        </Collapse>
      </Stack>

      {sys.has_groups && (
        <Stack gap={6} mt="md">
          <Text size="xs" tt="uppercase" fw={600} c="dimmed">
            Context — artifact groups (none = full snapshot)
          </Text>
          <Chip.Group multiple value={groups} onChange={setGroups}>
            <Group gap={8}>
              {allGroups.map(g => (
                <Chip key={g} value={g} size="sm" variant="outline">{g}</Chip>
              ))}
            </Group>
          </Chip.Group>
        </Stack>
      )}

      <Group mt="md" gap="lg">
        <Checkbox
          label="include unapproved" size="sm" checked={unapproved}
          onChange={e => setUnapproved(e.currentTarget.checked)}
        />
        <Checkbox
          label="grade after" size="sm" checked={gradeAfter}
          onChange={e => setGradeAfter(e.currentTarget.checked)}
        />
        {sys.has_web && (
          <Checkbox
            label="web search (live internet, +web)" size="sm" checked={webSearch}
            onChange={e => setWebSearch(e.currentTarget.checked)}
          />
        )}
      </Group>

      {msg && (
        <Alert
          mt="md" variant="light"
          color={msg.ok ? "teal" : "red"}
          icon={msg.ok ? <IconCheck size={16} /> : <IconAlertTriangle size={16} />}
          title={msg.ok ? `Launched ${msg.run}` : "Launch failed"}
        >
          <Code block style={{ fontSize: 11 }}>{msg.cmd}</Code>
        </Alert>
      )}
    </Paper>
    {sys.has_egress && <EgressEditor />}
    </>
  );
}
