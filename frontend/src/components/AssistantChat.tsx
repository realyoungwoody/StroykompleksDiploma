import{useState}from'react'
import{Bot,Check,MessageCircle,Send,ShoppingCart,X}from'lucide-react'
import{Link}from'react-router-dom'
import{api}from'../api/client'
import{useCart}from'../contexts/CartContext'
import{useToast}from'../contexts/ToastContext'
import type{Service}from'../types'
import{MarkdownMessage}from'./MarkdownMessage'
import{Button}from'./UI'

type CartAction={action:'add_to_cart'|'set_cart_quantity'|'remove_from_cart';service_id:number;name:string;unit:string;quantity:string;unit_price_rub:string;line_total_rub:string;note?:string}
type Msg={role:'user'|'assistant';content:string;mode?:string;warning?:string;cart_actions?:CartAction[];navigate_to?:string}
type ActionState='adding'|'added'|'error'
const rub=(value:string)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2}).format(Number(value))
const actionKey=(action:CartAction)=>`${action.action}:${action.service_id}:${action.quantity}:${action.note||''}`

export function AssistantChat(){
  const[open,setOpen]=useState(false),[input,setInput]=useState(''),[loading,setLoading]=useState(false)
  const[messages,setMessages]=useState<Msg[]>([{role:'assistant',content:'Здравствуйте! Помогу подобрать услугу и рассчитать предварительную стоимость.'}])
  const[actionStates,setActionStates]=useState<Record<string,ActionState>>({})
  const{items,add,addMany,setQuantity,remove}=useCart(),{notify}=useToast()

  const send=async(text=input)=>{
    if(!text.trim()||loading)return
    setInput('');setMessages(m=>[...m,{role:'user',content:text}]);setLoading(true)
    try{
      const contextActions=[...messages].reverse().find(message=>message.cart_actions?.length)?.cart_actions||[]
      const data=await api<{answer:string;mode:string;warning?:string;cart_actions?:CartAction[];navigate_to?:string}>('/assistant/chat',{method:'POST',body:JSON.stringify({message:text,history:messages.slice(-6).map(({role,content})=>({role,content})),context_actions:contextActions.map(({service_id,quantity,unit,note})=>({service_id,quantity,unit,note})),cart:items.map(item=>({service_id:item.service.id,quantity:item.quantity,note:item.note}))})})
      setMessages(m=>[...m,{role:'assistant',content:data.answer,mode:data.mode,warning:data.warning,cart_actions:data.cart_actions,navigate_to:data.navigate_to}])
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
      return{service,quantity,note:action.note,action}
    })
  }
  const addOne=async(action:CartAction)=>{
    const key=actionKey(action);if(actionStates[key]==='adding'||actionStates[key]==='added')return
    setActionStates(s=>({...s,[key]:'adding'}))
    try{const[entry]=await loadEntries([action]);let title='Добавлено в корзину';if(action.action==='remove_from_cart'){remove(entry.service.id);title='Удалено из корзины'}else if(action.action==='set_cart_quantity'){setQuantity(entry.service.id,entry.quantity,entry.note);title='Объём обновлён'}else{const result=add(entry.service,entry.quantity,entry.note);title=result==='updated'?'Количество обновлено':'Добавлено в корзину'}setActionStates(s=>({...s,[key]:'added'}));notify({type:'success',title,description:`${entry.service.name} — ${entry.quantity} ${entry.service.unit}`})}
    catch(e){setActionStates(s=>({...s,[key]:'error'}));notify({type:'error',title:'Не удалось выполнить действие',description:e instanceof Error?e.message:'Повторите попытку'})}
  }
  const addAll=async(actions:CartAction[])=>{
    const pending=actions.filter(action=>actionStates[actionKey(action)]!=='added')
    if(!pending.length||pending.some(action=>actionStates[actionKey(action)]==='adding'))return
    setActionStates(s=>({...s,...Object.fromEntries(pending.map(action=>[actionKey(action),'adding']))}))
    try{const entries=await loadEntries(pending);addMany(entries.map(({service,quantity,note})=>({service,quantity,note})));setActionStates(s=>({...s,...Object.fromEntries(pending.map(action=>[actionKey(action),'added']))}));notify({type:'success',title:'Все услуги добавлены',description:`Добавлено позиций: ${entries.length}`})}
    catch(e){setActionStates(s=>({...s,...Object.fromEntries(pending.map(action=>[actionKey(action),'error']))}));notify({type:'error',title:'Не удалось добавить услуги',description:e instanceof Error?e.message:'Корзина не изменена'})}
  }

  return <div className="assistant"><button className="assistant-fab" aria-label={open?'Закрыть ИИ-помощника':'Открыть ИИ-помощника'} aria-expanded={open} onClick={()=>setOpen(!open)}>{open?<X/>:<MessageCircle/>}</button>{open&&<section className="chat" aria-label="ИИ-помощник"><header><div><Bot/><span><b>Помощник</b><small>Не вводите персональные данные</small></span></div><button onClick={()=>setOpen(false)} aria-label="Закрыть"><X/></button></header><div className="quick">{['Что можно заказать?','Как оформить заявку?','Сколько стоит 20 м² штукатурки?'].map(q=><button key={q} disabled={loading} onClick={()=>send(q)}>{q}</button>)}</div><div className="messages" aria-live="polite">{messages.map((message,index)=><div key={index} className={`message ${message.role}`}>{message.role==='assistant'?<MarkdownMessage>{message.content}</MarkdownMessage>:message.content}{message.mode&&<small>{message.mode==='llm'?'ИИ подключён':'Демонстрационный помощник'}</small>}{message.warning&&<small className="message-warning">{message.warning}</small>}{message.cart_actions?.map(action=>{const state=actionStates[actionKey(action)],verb=action.action==='remove_from_cart'?'Убрать из корзины':action.action==='set_cart_quantity'?`Установить ${action.quantity} ${action.unit}`:`Добавить — ${action.quantity} ${action.unit}`;return <article className="assistant-cart-action" key={actionKey(action)}><div><b>{action.name}</b><span>{action.quantity} {action.unit} · {rub(action.line_total_rub)}</span>{action.note&&<em>{action.note}</em>}</div><Button loading={state==='adding'} loadingText="Выполняем…" disabled={state==='added'} onClick={()=>addOne(action)}>{state==='added'?<><Check/>Готово</>:state==='error'?<><ShoppingCart/>Повторить</>:<><ShoppingCart/>{verb}</>}</Button></article>})}{message.cart_actions&&message.cart_actions.length>1&&message.cart_actions.every(action=>action.action==='add_to_cart')&&<Button className="assistant-add-all" onClick={()=>addAll(message.cart_actions!)} disabled={message.cart_actions.every(action=>actionStates[actionKey(action)]==='added')}>Добавить всё в корзину</Button>}{(message.navigate_to||message.cart_actions?.some(action=>actionStates[actionKey(action)]==='added'))&&<Link className="assistant-cart-link" to={message.navigate_to||'/cart'} onClick={()=>setOpen(false)}>Перейти в корзину →</Link>}</div>)}{loading&&<div className="message assistant dots" role="status">Помощник подбирает информацию…</div>}</div><form onSubmit={event=>{event.preventDefault();send()}}><input aria-label="Сообщение помощнику" maxLength={1500} value={input} onChange={event=>setInput(event.target.value)} placeholder="Опишите задачу…"/><Button loading={loading} loadingText="" disabled={!input.trim()} aria-label="Отправить"><Send/></Button></form></section>}</div>
}
