import ReactMarkdown, {defaultUrlTransform} from 'react-markdown'
import remarkGfm from 'remark-gfm'

function safeUrl(url:string){
  if(url.startsWith('/')||url.startsWith('#'))return url
  try{
    const parsed=new URL(url)
    return ['http:','https:','mailto:'].includes(parsed.protocol)?defaultUrlTransform(url):''
  }catch{return ''}
}

export function MarkdownMessage({children}:{children:string}){
  return <div className="markdown-message"><ReactMarkdown
    remarkPlugins={[remarkGfm]}
    skipHtml
    urlTransform={safeUrl}
    components={{
      a:({node:_,href,children,...props})=>href?<a {...props} href={href} target="_blank" rel="noopener noreferrer">{children}</a>:<span>{children}</span>,
      table:({node:_,...props})=><div className="markdown-table"><table {...props}/></div>,
      img:()=>null,
    }}
  >{children}</ReactMarkdown></div>
}
