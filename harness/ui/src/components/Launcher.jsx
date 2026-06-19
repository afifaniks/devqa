import { useState } from "react";
import {
  Paper, Group, Stack, Select, Autocomplete, NumberInput, Checkbox, Button,
  Chip, Text, Code, Alert,
} from "@mantine/core";
import { IconPlayerPlay, IconCheck, IconAlertTriangle } from "@tabler/icons-react";
import { api } from "../api.js";

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
  const [limit, setLimit] = useState("");
  const [unapproved, setUnapproved] = useState(false);
  const [force, setForce] = useState(false);
  const [gradeAfter, setGradeAfter] = useState(true);
  const [judge, setJudge] = useState("openai/gpt-5.4");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);

  const systems = options.systems || [];
  const sys = systems.find(s => s.id === system) || {};
  const allGroups = options.groups || [];

  const launch = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.launch({
        system,
        model: sys.needs_model || model ? model || null : null,
        groups: sys.has_groups && groups.length ? groups : null,
        limit: limit ? parseInt(limit, 10) : null,
        include_unapproved: unapproved,
        force,
        grade_after: gradeAfter,
        judge: gradeAfter ? judge : null,
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
          label="force re-run" size="sm" checked={force}
          onChange={e => setForce(e.currentTarget.checked)}
        />
        <Checkbox
          label="grade after" size="sm" checked={gradeAfter}
          onChange={e => setGradeAfter(e.currentTarget.checked)}
        />
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
  );
}
