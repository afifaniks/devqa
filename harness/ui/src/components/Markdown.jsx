import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { TypographyStylesProvider } from "@mantine/core";

// Render maintainer/issue Markdown (GFM) with Mantine-styled typography. Links open in a
// new tab. TypographyStylesProvider gives headings/lists/code/tables theme-consistent
// styling without hand-written CSS.
export function Markdown({ children, fontSize = 13.5 }) {
  return (
    <TypographyStylesProvider style={{ fontSize }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {children || ""}
      </ReactMarkdown>
    </TypographyStylesProvider>
  );
}
