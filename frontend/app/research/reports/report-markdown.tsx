import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Root, RootContent } from "mdast";
import { reportHeadingSlug, safeResearchReportLink, type ResearchReportTarget } from "@/lib/research-reports";

export type ReportHeading = { id: string; text: string; depth: number };

function nodeText(node: RootContent): string {
  if ("value" in node) return node.value;
  if ("alt" in node) return node.alt ?? "";
  return "children" in node ? node.children.map(nodeText).join("") : "";
}

/** Parse once so the outline and the rendered headings always share the same IDs. */
export function renderResearchReport(markdown: string, target: ResearchReportTarget) {
  const headings: ReportHeading[] = [];
  const usedIds = new Set<string>();
  function reportHeadings() {
    return (tree: Root): void => {
      function walk(nodes: RootContent[]): void {
        for (const node of nodes) {
          if (node.type === "heading") {
            const text = nodeText(node);
            const base = `report-${reportHeadingSlug(text)}`;
            let id = base;
            let suffix = 2;
            while (usedIds.has(id)) id = `${base}-${suffix++}`;
            usedIds.add(id);
            node.data = { ...node.data, hProperties: { ...node.data?.hProperties, id } };
            headings.push({ id, text, depth: node.depth });
          }
          if ("children" in node) walk(node.children);
        }
      }
      walk(tree.children);
    };
  }
  const components: Components = {
    a: ({ children, href, id, "aria-describedby": describedBy, "aria-label": label, node }) => href ? <a
      href={href}
      id={id}
      aria-describedby={describedBy}
      aria-label={label}
      data-footnote-ref={node?.properties.dataFootnoteRef === true ? "" : undefined}
      data-footnote-backref={node?.properties.dataFootnoteBackref === "" ? "" : undefined}
      rel={/^https?:/.test(href) ? "noreferrer noopener" : undefined}
    >{children}</a> : <span title="지원하지 않는 주소입니다">{children}</span>,
    img: ({ alt, src }) => <span className="report-image-reference">이미지: {alt || "설명 없음"}{typeof src === "string" && src && <> · <a href={src} rel="noreferrer noopener">이미지 주소 열기</a></>}</span>,
    table: ({ children }) => <div className="report-table-scroll" role="region" aria-label="보고서 표 · 가로로 이동 가능" tabIndex={0}><table>{children}</table></div>,
  };
  const body = Markdown({
    children: markdown,
    remarkPlugins: [remarkGfm, reportHeadings],
    components,
    skipHtml: false,
    urlTransform: (url) => safeResearchReportLink(url, target),
    remarkRehypeOptions: { footnoteLabel: "각주", footnoteBackLabel: "본문으로 돌아가기" },
  });
  return { body, headings };
}
