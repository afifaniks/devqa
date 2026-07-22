import { useState, useEffect } from "react";
import {
  Paper, Stack, Group, Text, Checkbox, TagsInput, Button, Badge,
} from "@mantine/core";
import { IconShieldLock, IconDeviceFloppy } from "@tabler/icons-react";
import { api } from "../api.js";

// Editor for the container egress allowlist (persisted server-side via GET/PUT /api/egress).
// Restricted container runs can reach ONLY the effective allowlist; everything else — github,
// package registries, arbitrary web — is dropped at the firewall. The +web launch toggle
// overrides this with open internet for the run. New runs pick up a saved allowlist with no
// restart. Shown in the launcher only when the selected system is egress-controlled.
export function EgressEditor() {
  const [data, setData] = useState(null);
  const [providers, setProviders] = useState([]);
  const [extra, setExtra] = useState([]);
  const [ollama, setOllama] = useState(true);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const apply = d => {
    setData(d);
    setProviders(d.config.providers);
    setExtra(d.config.extra_domains);
    setOllama(d.config.allow_ollama);
  };

  useEffect(() => { api.getEgress().then(apply).catch(() => {}); }, []);

  if (!data) return null;

  const save = async () => {
    setBusy(true);
    setSaved(false);
    try {
      const d = await api.saveEgress({
        providers, extra_domains: extra, allow_ollama: ollama,
      });
      setData(prev => ({ ...prev, ...d, config: d.config }));
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Paper withBorder p="md" radius="md" mt="md">
      <Group justify="space-between" mb="xs">
        <Group gap={8}>
          <IconShieldLock size={16} />
          <Text fw={600} size="sm">Container egress allowlist</Text>
        </Group>
        <Button
          size="xs" variant="light" color={saved ? "teal" : "blue"}
          leftSection={<IconDeviceFloppy size={14} />} loading={busy} onClick={save}
        >
          {saved ? "Saved" : "Save allowlist"}
        </Button>
      </Group>
      <Text size="xs" c="dimmed" mb="md">
        Restricted runs reach only the hosts below; github, registries and arbitrary web are
        blocked at the firewall. (The “web search (+web)” toggle overrides this with open internet.)
      </Text>

      <Group align="flex-start" gap={48} wrap="wrap">
        <Stack gap={6}>
          <Text size="xs" tt="uppercase" fw={600} c="dimmed">Model providers</Text>
          {data.available_providers.map(p => (
            <Checkbox
              key={p} size="sm" label={p} checked={providers.includes(p)}
              onChange={e => setProviders(
                e.currentTarget.checked ? [...providers, p] : providers.filter(x => x !== p))}
            />
          ))}
          <Checkbox
            size="sm" mt={4} label="host Ollama (10.0.2.2:11434)" checked={ollama}
            onChange={e => setOllama(e.currentTarget.checked)}
          />
        </Stack>

        <Stack gap={6} style={{ flex: 1, minWidth: 300 }}>
          <Text size="xs" tt="uppercase" fw={600} c="dimmed">
            Extra domains (subdomains included)
          </Text>
          <TagsInput
            value={extra} onChange={setExtra} clearable
            placeholder="add a domain, e.g. pypi.org, then Enter"
          />
          <Text size="xs" c="dimmed">
            Always allowed: {data.vuln_domains.join(", ")} — CVE/GHSA/CWE lookup
          </Text>
        </Stack>
      </Group>

      <Text size="xs" tt="uppercase" fw={600} c="dimmed" mt="md" mb={6}>
        Effective allowlist
      </Text>
      <Group gap={6}>
        {data.effective_domains.map(d => (
          <Badge key={d} variant="light" size="sm">{d}</Badge>
        ))}
        {data.hosts.map(h => (
          <Badge key={h} variant="light" color="grape" size="sm">{h}</Badge>
        ))}
      </Group>
    </Paper>
  );
}
