// Arabic lens, server side: wraps the glossary terms of a lesson in <span class="gloss"
// data-term="i"> (remark plugin). The spans are inert until the lens is switched on.

interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

// Never inside source chips, code, links or headings (headings stay clean).
const SKIP = new Set(["citation", "inlineCode", "code", "link", "heading"]);

const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const fold = (value: string) => value.normalize("NFC").toLocaleLowerCase("fr");

export function remarkGlossary(options: { terms: string[] }) {
  const terms = options.terms.filter(Boolean);
  return (tree: MdNode) => {
    if (terms.length === 0) return;
    const index = new Map(terms.map((term, position) => [fold(term), position]));
    const pattern = new RegExp(
      // Plurals in -s/-x match too ("œdèmes").
      `(?<![\\p{L}\\p{N}])(?:${[...terms].sort((a, b) => b.length - a.length).map(escape).join("|")})(?:s|x)?(?![\\p{L}\\p{N}])`,
      "giu",
    );

    const split = (node: MdNode): MdNode[] => {
      const value = node.value ?? "";
      const parts: MdNode[] = [];
      let last = 0;
      for (const match of value.matchAll(pattern)) {
        const start = match.index ?? 0;
        if (start > last) parts.push({ type: "text", value: value.slice(last, start) });
        const key = fold(match[0]);
        const term = index.get(key) ?? index.get(key.replace(/[sx]$/u, "")) ?? 0;
        parts.push({
          type: "glossTerm",
          children: [{ type: "text", value: match[0] }],
          data: { hName: "span", hProperties: { className: ["gloss"], dataTerm: String(term) } },
        });
        last = start + match[0].length;
      }
      if (parts.length === 0) return [node];
      if (last < value.length) parts.push({ type: "text", value: value.slice(last) });
      return parts;
    };

    const walk = (node: MdNode) => {
      if (!node.children || SKIP.has(node.type)) return;
      node.children = node.children.flatMap((child) => {
        if (child.type === "text") return split(child);
        walk(child);
        return [child];
      });
    };
    walk(tree);
  };
}
