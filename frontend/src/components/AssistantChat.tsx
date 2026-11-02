import{useState}from'react'
import{Bot,Check,MessageCircle,Send,ShoppingCart,X}from'lucide-react'
import{Link}from'react-router-dom'
import{api}from'../api/client'
import{useCart}from'../contexts/CartContext'
import{useToast}from'../contexts/ToastContext'
import type{Service}from'../types'
import{MarkdownMessage}from'./MarkdownMessage'
import{Button}from'./UI'

type CartAction={action:'add_to_cart';service_id:number;name:string;unit:string;quantity:string;unit_price_rub:string;line_total_rub:string}
type Msg={role:'user'|'assistant';content:string;mode?:string;warning?:string;cart_actions?:CartAction[]}
type ActionState='adding'|'added'|'error'
const rub=(value:string)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2}).format(Number(value))

export function AssistantChat(){
  const[open,setOpen]=useState(false),[input,setInput]=useState(''),[loading,setLoading]=useState(false)
  const[messages,setMessages]=useState<Msg[]>([{role:'assistant',content:'Здравствуйте! Помогу подобрать услугу и рассчитать предварительную стоимость.'}])
  const[actionStates,setActionStates]=useState<Record<number,ActionState>>({})
  const{add,addMany}=useCart(),{notify}=useToast()

  const send=async(text=input)=>{
    if(!text.trim()||loading)return
    setInput('');setMessages(m=>[...m,{role:'user',content:text}]);setLoading(true)
    try{
      const data=await api<{answer:string;mode:string;warning?:string;cart_actions?:CartAction[]}>('/assistant/chat',{method:'POST',body:JSON.stringify({message:text,history:messages.slice(-6).map(({role,content})=>({role,content}))})})
      setMessages(m=>[...m,{role:'assistant',content:data.answer,mode:data.mode,warning:data.warning,cart_actions:data.cart_actions}])
      if(data.warning)notify({type:'warning',title:'ИИ API недоступен',description:data.warning})
    }catch(e){const message=e instanceof Error?e.message:'Помощник временно недоступен';setMessages(m=>[...m,{role:'assistant',content:message}]);notify({type:'error',title:'Помощник недоступен',description:message})}
    finally{setLoading(false)}
  }

  const loadEntries=async(actions:CartAction[])=>{
    const services=await api<Service[]>('/services')
    return actions.map(action=>{
      const service=services.find(item=>item.id===action.service_id&&item.is_active)
      const quantity=Number(action.quantity)
      if(!service||service.unit!==action.unit||!Number.isFinite(quantity)||quantity<.1||quantity>10000)throw new Error(`Услуга «${action.name}» недоступна или изменилась`)
      return{service,quantity,action}
    })
  }
  const addOne=async(action:CartAction)=>{
    if(actionStates[action.service_id]==='adding'||actionStates[action.service_id]==='added')return
    setActionStates(s=>({...s,[action.service_id]:'adding'}))
    try{const[entry]=await loadEntries([action]);const result=add(entry.service,entry.quantity);setActionStates(s=>({...s,[action.service_id]:'added'}));notify({type:'success',title:result==='updated'?'Количество обновлено':'Добавлено в корзину',description:`${entry.service.name} — ${entry.quantity} ${entry.service.unit}`})}
    catch(e){setActionStates(s=>({...s,[action.service_id]:'error'}));notify({type:'error',title:'Не удалось добавить услугу',description:e instanceof Error?e.message:'Повторите попытку'})}
  }
  const addAll=async(actions:CartAction[])=>{
    const pending=actions.filter(action=>actionStates[action.service_id]!=='added')
    if(!pending.length||pending.some(action=>actionStates[action.service_id]==='adding'))return
    setActionStates(s=>({...s,...Object.fromEntries(pending.map(action=>[action.service_id,'adding']))}))
    try{const entries=await loadEntries(pending);addMany(entries.map(({service,quantity})=>({service,quantity})));setActionStates(s=>({...s,...Object.fromEntries(pending.map(action=>[action.service_id,'added']))}));notify({type:'success',title:'Все услуги добавлены',description:`Добавлено позиций: ${entries.length}`})}
    catch(e){setActionStates(s=>({...s,...Object.fromEntries(pending.map(action=>[action.service_id,'error']))}));notify({type:'error',title:'Не удалось добавить услуги',description:e instanceof Error?e.message:'Корзина не изменена'})}
  }

  return <div className="assistant"><button className="assistant-fab" aria-label={open?'Закрыть ИИ-помощника':'Открыть ИИ-помощника'} aria-expanded={open} onClick={()=>setOpen(!open)}>{open?<X/>:<MessageCircle/>}</button>{open&&<section className="chat" aria-label="ИИ-помощник"><header><div><Bot/><span><b>Помощник</b><small>Не вводите персональные данные</small></span></div><button onClick={()=>setOpen(false)} aria-label="Закрыть"><X/></button></header><div className="quick">{['Что можно заказать?','Как оформить заявку?','Сколько стоит 20 м² штукатурки?'].map(q=><button key={q} disabled={loading} onClick={()=>send(q)}>{q}</button>)}</div><div className="messages" aria-live="polite">{messages.map((message,index)=><div key={index} className={`message ${message.role}`}>{message.role==='assistant'?<MarkdownMessage>{message.content}</MarkdownMessage>:message.content}{message.mode&&<small>{message.mode==='llm'?'ИИ подключён':'Демонстрационный помощник'}</small>}{message.warning&&<small className="message-warning">{message.warning}</small>}{message.cart_actions?.map(action=>{const state=actionStates[action.service_id];return <article className="assistant-cart-action" key={action.service_id}><div><b>{action.name}</b><span>{action.quantity} {action.unit} · {rub(action.line_total_rub)}</span></div><Button loading={state==='adding'} loadingText="Добавляем…" disabled={state==='added'} onClick={()=>addOne(action)}>{state==='added'?<><Check/>Добавлено</>:state==='error'?<><ShoppingCart/>Повторить</>:<><ShoppingCart/>Добавить — {action.quantity} {action.unit}</>}</Button></article>})}{message.cart_actions&&message.cart_actions.length>1&&<Button className="assistant-add-all" onClick={()=>addAll(message.cart_actions!)} disabled={message.cart_actions.every(action=>actionStates[action.service_id]==='added')}>Добавить всё в корзину</Button>}{message.cart_actions?.some(action=>actionStates[action.service_id]==='added')&&<Link className="assistant-cart-link" to="/cart" onClick={()=>setOpen(false)}>Перейти в корзину →</Link>}</div>)}{loading&&<div className="message assistant dots" role="status">Помощник подбирает информацию…</div>}</div><form onSubmit={event=>{event.preventDefault();send()}}><input aria-label="Сообщение помощнику" maxLength={1500} value={input} onChange={event=>setInput(event.target.value)} placeholder="Опишите задачу…"/><Button loading={loading} loadingText="" disabled={!input.trim()} aria-label="Отправить"><Send/></Button></form></section>}</div>
}
