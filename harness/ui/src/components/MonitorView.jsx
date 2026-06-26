import { useState } from "react";
import { Text, Code } from "@mantine/core";
import { Launcher } from "./Launcher.jsx";
import { ProcessList } from "./ProcessList.jsx";
import { RunCard } from "./RunCard.jsx";
import { SectionLabel } from "./SectionLabel.jsx";

// Launch evaluations and watch them run, live. Runs + procs arrive already
// polled from <App/>, so this view re-renders as the data updates.
export function MonitorView({ options, runs, totals, procs, onLaunched, onStopProc, onRemoveProc, onRefresh }) {
  const [open, setOpen] = useState(null);

  const handleDeleted = name => {
    if (open === name) setOpen(null);
    onRefresh?.();
  };

  return (
    <>
      <SectionLabel mt="xs">Launch a run</SectionLabel>
      <Launcher options={options} onLaunched={onLaunched} />

      {procs.length > 0 && (
        <>
          <SectionLabel count={`${procs.length} this session`}>Launched processes</SectionLabel>
          <ProcessList procs={procs} onStop={onStopProc} onRemove={onRemoveProc} />
        </>
      )}

      <SectionLabel count={`${runs.length} total`}>Runs</SectionLabel>
      {runs.length === 0 ? (
        <Text c="dimmed" ta="center" py="xl">
          No runs yet — launch one above, or from the shell:{" "}
          <Code>python -m harness agent --model gpt-5.4-mini</Code>
        </Text>
      ) : (
        runs.map(r => (
          <RunCard
            key={r.name} run={r} totals={totals}
            open={open === r.name}
            onToggle={n => setOpen(open === n ? null : n)}
            onDeleted={handleDeleted}
          />
        ))
      )}
    </>
  );
}
