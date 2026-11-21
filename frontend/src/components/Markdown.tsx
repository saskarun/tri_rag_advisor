import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Renders LLM markdown (GFM tables, lists, code). [S1] / [S1, Clause 3] become clickable citation chips. */
export default function Markdown({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  const prepared = text.replace(/\[S(\d+)(?:[^\]]*)\]/g, (_m, n) => `[S${n}](#cite-${n})`)
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const m = href?.match(/^#cite-(\d+)$/)
            if (m) return <button className="cite" onClick={() => onCite?.(Number(m[1]))}>{children}</button>
            return <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2">{children}</a>
          },
          table: ({ children }) => <div className="tbl"><table>{children}</table></div>,
        }}>{prepared}</ReactMarkdown>
    </div>
  )
}
