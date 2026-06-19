import { createTheme } from "@mantine/core";

// Identity: a security-evaluation *instrument*. The grading verdict colors
// (correct / partial / incorrect) are the signature visual language and appear
// everywhere a prediction is judged. One calm azure carries interaction; the
// rest stays quiet. IBM Plex Mono for data (qids, CVE IDs), Plex Sans for chrome.

const azure = [
  "#e8f1ff", "#cfe0ff", "#9dc0ff", "#699fff", "#4084fb",
  "#2773f5", "#155fe0", "#0a4dc4", "#003e9f", "#00337f",
];

export const theme = createTheme({
  primaryColor: "azure",
  primaryShade: 5,
  colors: { azure },
  fontFamily: "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
  fontFamilyMonospace: "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace",
  headings: { fontFamily: "'IBM Plex Sans', system-ui, sans-serif", fontWeight: "600" },
  defaultRadius: "md",
  cursorType: "pointer",
  components: {
    Tooltip: { defaultProps: { withArrow: true, openDelay: 200 } },
  },
});

// Verdict → Mantine color name. Used for Badge/Progress/spine across the app.
export const VERDICT_COLOR = {
  correct: "teal",
  partial: "yellow",
  incorrect: "red",
  error: "orange",
  ungraded: "gray",
  running: "teal",
  agent: "violet",
};
