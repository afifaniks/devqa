import { useEffect, useState } from "react";
import {
  AppShell, Group, Tabs, Text, Badge, Box, Container, Indicator,
} from "@mantine/core";
import { IconFlask, IconActivity, IconColumns3 } from "@tabler/icons-react";
import { usePolling } from "./hooks/usePolling.js";
import { api } from "./api.js";
import { MonitorView } from "./components/MonitorView.jsx";
import { CompareView } from "./components/compare/CompareView.jsx";

export function App() {
  const [tab, setTab] = useState("monitor");
  const [options, setOptions] = useState({});

  // Options change rarely — fetch once. Runs + procs poll live and are shared
  // with both the header stats and the Monitor view.
  useEffect(() => { api.options().then(setOptions).catch(() => {}); }, []);
  const runsPoll = usePolling(api.runs, 3000);
  const procsPoll = usePolling(api.procs, 3000);

  const runs = runsPoll.data?.runs ?? [];
  const totals = runsPoll.data?.totals ?? {};
  const procs = procsPoll.data?.procs ?? [];
  const anyRunning = runs.some(r => r.running) || procs.some(p => p.running);

  const refresh = () => { runsPoll.refresh(); procsPoll.refresh(); };

  return (
    <AppShell header={{ height: 56 }} padding={0}>
      <AppShell.Header
        withBorder
        style={{
          background: "rgba(20,24,33,.82)",
          backdropFilter: "blur(10px)",
        }}
      >
        <Group h="100%" px="md" gap="lg" wrap="nowrap">
          <Group gap={8} wrap="nowrap">
            <IconFlask size={20} color="var(--mantine-color-azure-4)" />
            <Text fw={600} style={{ letterSpacing: ".2px" }}>
              SecDevQA <Text span c="azure.4" fw={700}>harness</Text>
            </Text>
          </Group>

          <Tabs value={tab} onChange={setTab} variant="default">
            <Tabs.List style={{ borderBottom: "none" }}>
              <Tabs.Tab value="monitor" leftSection={<IconActivity size={15} />}>
                Monitor
              </Tabs.Tab>
              <Tabs.Tab value="compare" leftSection={<IconColumns3 size={15} />}>
                Compare
              </Tabs.Tab>
            </Tabs.List>
          </Tabs>

          <Group gap="lg" ml="auto" wrap="nowrap">
            <Indicator
              color="teal" size={8} processing disabled={!anyRunning}
              position="middle-start" offset={-2}
            >
              <Text size="xs" c="dimmed" pl={anyRunning ? 12 : 0}>
                <Text span c="bright" fw={600} ff="monospace">{runs.length}</Text> runs
              </Text>
            </Indicator>
            <Text size="xs" c="dimmed">
              items{" "}
              <Text span c="bright" fw={600} ff="monospace">
                {totals.items_approved ?? "…"}
              </Text>{" "}
              approved /{" "}
              <Text span ff="monospace">{totals.items_total ?? "…"}</Text> total
            </Text>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Container size={1500} py="lg" px="md">
          <Box display={tab === "monitor" ? "block" : "none"}>
            <MonitorView
              options={options}
              runs={runs}
              totals={totals}
              procs={procs}
              onLaunched={refresh}
              onRefresh={refresh}
              onStopProc={async id => { await api.stopProc(id); refresh(); }}
            />
          </Box>
          <Box display={tab === "compare" ? "block" : "none"}>
            <CompareView runs={runs} />
          </Box>
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
