import{useEffect,useRef,useState}from'react'
import{Bot,Check,MessageCircle,RotateCcw,Send,ShoppingCart,X}from'lucide-react'
import{Link}from'react-router-dom'
import{api}from'../api/client'
import{useCart}from'../contexts/CartContext'
import{useToast}from'../contexts/ToastContext'
import type{Quote,Service}from'../types'
import{MarkdownMessage}from'./MarkdownMessage'
import{Button}from'./UI'

type CartAction={
  action:'add_to_cart'|'set_cart_quantity'|'remove_from_cart'
  calculation_id:string
  conversation_id:string
  service_id:number
  name:string
  unit:string
  quantity:string
  unit_price_rub:string
  line_total_rub:string
  note?:string
  selection_item_id?:string
  selection_revision?:number
}
type SelectionItem={selection_item_id:string;kind:string;service_id?:number;name:string;quantity?:string;unit:string;note?:string;status:'incomplete'|'ready'|'invalid'|'added';missing_parameters:string[];unit_price_rub?:string;line_total_rub?:string;can_add_to_cart:boolean;added:boolean}
type SelectionState={conversation_id:string;revision:number;items:SelectionItem[];diagnostics?:string[]}
type Msg={role:'user'|'assistant';content:string;mode?:string;warning?:string;navigate_to?:string}
type ActionState='adding'|'added'|'error'
type ActiveCalculation={id:string;actions:CartAction[]}
type SavedChat={conversationId:string;selection:SelectionState|null;activeCalculation:ActiveCalculation|null;actionStates:Record<string,ActionState>}

const greeting:Msg={role:'assistant',content:'Здравствуйте! Помогу подобрать услугу и рассчитать предварительную стоимость.'}
const rub=(value:string)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2}).format(Number(value))
const newConversationId=()=>`chat-${globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`}`
const actionKey=(action:CartAction)=>`${action.calculation_id}:${action.action}:${action.service_id}`
const storageKey='sk-assistant-selection-v1'
const loadChat=():SavedChat|null=>{try{return JSON.parse(localStorage.getItem(storageKey)||'null')}catch{return null}}

export function AssistantChat(){
  const restored=useRef(loadChat()).current
  const[open,setOpen]=useState(false),[input,setInput]=useState(''),[loading,setLoading]=useState(false)
  const[messages,setMessages]=useState<Msg[]>([greeting])
  const[selection,setSelection]=useState<SelectionState|null>(restored?.selection||null)
  const[activeCalculation,setActiveCalculation]=useState<ActiveCalculation|null>(restored?.activeCalculation||null)
  const[actionStates,setActionStates]=useState<Record<string,ActionState>>(restored?.actionStates||{})
  const conversationId=useRef(restored?.conversationId||newConversationId()),requestVersion=useRef(0),abortRequest=useRef<AbortController|null>(null),actionLocks=useRef(new Set<string>())
  const{items,add,addMany,setQuantity,remove}=useCart(),{notify}=useToast()

  useEffect(()=>()=>{abortRequest.current?.abort();requestVersion.current+=1},[])
  useEffect(()=>localStorage.setItem(storageKey,JSON.stringify({conversationId:conversationId.current,selection,activeCalculation,actionStates})),[selection,activeCalculation,actionStates])

  const resetConversation=()=>{
    abortRequest.current?.abort();requestVersion.current+=1;conversationId.current=newConversationId()
    setMessages([greeting]);setSelection(null);setActiveCalculation(null);setActionStates({});setInput('');setLoading(false)
  }

  const send=async(text=input)=>{
    const clean=text.trim();if(!clean)return
    const context=activeCalculation
    const version=++requestVersion.current
    abortRequest.current?.abort();const controller=new AbortController();abortRequest.current=controller
    setInput('');setMessages(current=>[...current,{role:'user',content:clean}]);setLoading(true)
    try{
      const data=await api<{answer:string;mode:string;warning?:string;cart_actions?:CartAction[];calculation_id?:string;navigate_to?:string;selection?:SelectionState}>('/assistant/chat',{method:'POST',signal:controller.signal,body:JSON.stringify({message:clean,conversation_id:conversationId.current,history:messages.slice(-6).map(({role,content})=>({role,content})),context_calculation_id:context?.id,context_actions:(context?.actions||[]).map(({calculation_id,conversation_id,service_id,quantity,unit,note})=>({calculation_id,conversation_id,service_id,quantity,unit,note})),cart:items.map(item=>({service_id:item.service.id,quantity:item.quantity,note:item.note})),selection})})
      if(version!==requestVersion.current)return
      const actions=data.calculation_id&&data.cart_actions?.every(action=>action.calculation_id===data.calculation_id&&action.conversation_id===conversationId.current)?data.cart_actions:[]
      setMessages(current=>[...current,{role:'assistant',content:data.answer,mode:data.mode,warning:data.warning,navigate_to:data.navigate_to}])
      if(data.selection?.conversation_id===conversationId.current)setSelection(data.selection)
      setActiveCalculation(data.calculation_id&&actions.length?{id:data.calculation_id,actions}:null)
      if(data.warning)notify({type:'warning',title:'ИИ временно недоступен',description:data.warning})
    }catch(error){
      if(controller.signal.aborted||version!==requestVersion.current)return
      const message=error instanceof Error?error.message:'Помощник временно недоступен'
      setMessages(current=>[...current,{role:'assistant',content:message}]);notify({type:'error',title:'Помощник недоступен',description:message})
    }finally{if(version===requestVersion.current)setLoading(false)}
  }

  const validateEntries=async(actions:CartAction[])=>{
    const services=await api<Service[]>('/services')
    const entries=actions.map(action=>{
      const service=services.find(item=>item.id===action.service_id&&item.is_active),quantity=Number(action.quantity)
      if(!service||service.unit!==action.unit||!Number.isFinite(quantity)||quantity<.1||quantity>10000)throw new Error(`Услуга «${action.name}» недоступна или изменилась`)
      return{service,quantity,note:action.note,action}
    })
    const priced=actions.filter(action=>action.action!=='remove_from_cart')
    if(priced.length){
      const quote=await api<Quote>('/quotes',{method:'POST',body:JSON.stringify({items:priced.map(action=>({service_id:action.service_id,quantity:action.quantity}))})})
      for(const action of priced){const line=quote.items.find(item=>item.service_id===action.service_id);if(!line||line.unit!==action.unit||Number(line.unit_price_rub)!==Number(action.unit_price_rub)||Number(line.line_total_rub)!==Number(action.line_total_rub))throw new Error('Цена услуги изменилась. Выполните расчёт повторно.')}
    }
    return entries
  }

  const isCurrent=(action:CartAction)=>activeCalculation?.id===action.calculation_id&&action.conversation_id===conversationId.current
  const addOne=async(action:CartAction)=>{
    const key=actionKey(action)
    if(!isCurrent(action)||actionLocks.current.has(key)||actionStates[key]==='added')return
    actionLocks.current.add(key);setActionStates(state=>({...state,[key]:'adding'}))
    try{
      const[entry]=await validateEntries([action]);let title='Добавлено в корзину'
      if(action.action==='remove_from_cart'){remove(entry.service.id);title='Удалено из корзины'}
      else if(action.action==='set_cart_quantity'){setQuantity(entry.service.id,entry.quantity,entry.note);title='Объём обновлён'}
      else{const result=add(entry.service,entry.quantity,entry.note);title=result==='updated'?'Количество обновлено':'Добавлено в корзину'}
      setActionStates(state=>({...state,[key]:'added'}));setSelection(current=>current?{...current,items:current.items.map(item=>item.service_id===action.service_id?{...item,status:'added',added:true,can_add_to_cart:false}:item)}:current);notify({type:'success',title,description:`${entry.service.name} — ${entry.quantity} ${entry.service.unit}`})
    }catch(error){setActionStates(state=>({...state,[key]:'error'}));notify({type:'error',title:'Не удалось выполнить действие',description:error instanceof Error?error.message:'Повторите попытку'})}
    finally{actionLocks.current.delete(key)}
  }

  const addAll=async(actions:CartAction[])=>{
    if(!actions.length||actions.some(action=>!isCurrent(action)))return
    const groupKey=`all:${activeCalculation?.id}`
    if(actionLocks.current.has(groupKey))return
    const pending=actions.filter(action=>actionStates[actionKey(action)]!=='added')
    if(!pending.length)return
    actionLocks.current.add(groupKey);setActionStates(state=>({...state,...Object.fromEntries(pending.map(action=>[actionKey(action),'adding']))}))
    try{const entries=await validateEntries(pending);addMany(entries.map(({service,quantity,note})=>({service,quantity,note})));setActionStates(state=>({...state,...Object.fromEntries(pending.map(action=>[actionKey(action),'added']))}));const addedIds=new Set(pending.map(action=>action.service_id));setSelection(current=>current?{...current,items:current.items.map(item=>item.service_id&&addedIds.has(item.service_id)?{...item,status:'added',added:true,can_add_to_cart:false}:item)}:current);notify({type:'success',title:'Все услуги добавлены',description:`Добавлено позиций: ${entries.length}`})}
    catch(error){setActionStates(state=>({...state,...Object.fromEntries(pending.map(action=>[actionKey(action),'error']))}));notify({type:'error',title:'Не удалось добавить услуги',description:error instanceof Error?error.message:'Корзина не изменена'})}
    finally{actionLocks.current.delete(groupKey)}
  }

  const actions=activeCalculation?.actions||[]
  const renderAction=(action:CartAction)=>{const state=actionStates[actionKey(action)],current=isCurrent(action),verb=action.action==='remove_from_cart'?'Убрать из корзины':action.action==='set_cart_quantity'?`Установить ${action.quantity} ${action.unit}`:`Добавить — ${action.quantity} ${action.unit}`;return <article className={`assistant-cart-action${current?'':' stale'}`} key={actionKey(action)}><div><b>{action.name}</b><span>{action.quantity} {action.unit} · {rub(action.line_total_rub)}</span>{action.note&&<em>{action.note}</em>}</div><Button loading={state==='adding'} loadingText="Добавляем…" disabled={!current||state==='added'} onClick={()=>addOne(action)}>{!current?'Расчёт устарел':state==='added'?<><Check/>Добавлено в корзину</>:state==='error'?<><ShoppingCart/>Повторить</>:<><ShoppingCart/>{verb}</>}</Button></article>}
  const showSelection=Boolean(selection?.items.length||actions.length)

  return <div className="assistant"><button className="assistant-fab" aria-label={open?'Закрыть ИИ-помощника':'Открыть ИИ-помощника'} aria-expanded={open} onClick={()=>setOpen(!open)}>{open?<X/>:<MessageCircle/>}</button>{open&&<section className="chat" aria-label="ИИ-помощник"><header><div><Bot/><span><b>Помощник</b><small>Не вводите персональные данные</small></span></div><div className="chat-header-actions"><button onClick={resetConversation} aria-label="Новый диалог"><RotateCcw/></button><button onClick={()=>setOpen(false)} aria-label="Закрыть"><X/></button></div></header><div className="quick">{['Что можно заказать?','Как оформить заявку?','Сколько стоит 20 м² штукатурки?'].map(question=><button key={question} onClick={()=>send(question)}>{question}</button>)}</div><div className="messages" aria-live="polite">{messages.map((message,index)=><div key={index} className={`message ${message.role}`}>{message.role==='assistant'?<MarkdownMessage>{message.content}</MarkdownMessage>:message.content}{message.mode&&<small>{message.mode==='llm'?'ИИ подключён':'Демонстрационный помощник'}</small>}{message.warning&&<small className="message-warning">{message.warning}</small>}{message.navigate_to&&<Link className="assistant-cart-link" to={message.navigate_to} onClick={()=>setOpen(false)}>Перейти в корзину →</Link>}</div>)}{loading&&<div className="message assistant dots" role="status">Помощник обновляет расчёт…</div>}</div>{showSelection&&<section className="assistant-selection" aria-label="Подобранные услуги"><div className="assistant-selection-title"><b>Подобранные услуги</b>{selection&&<small>Версия {selection.revision}</small>}</div>{selection?selection.items.map(item=>{const action=actions.find(candidate=>candidate.selection_item_id===item.selection_item_id)||actions.find(candidate=>candidate.service_id===item.service_id);if(action)return renderAction(action);return <article className="assistant-cart-action incomplete" key={item.selection_item_id}><div><b>{item.name}</b>{item.quantity&&<span>{item.quantity} {item.unit}{item.line_total_rub?` · ${rub(item.line_total_rub)}`:''}</span>}{item.note&&<em>{item.note}</em>}{item.status==='incomplete'&&<span>Нужно уточнить: {item.missing_parameters.join(', ')}</span>}</div><Button disabled>{item.status==='added'?<><Check/>Добавлено в корзину</>:item.status==='invalid'?'Расчёт недоступен':'Ожидает уточнения'}</Button></article>}):actions.map(renderAction)}{actions.length>1&&actions.every(action=>action.action==='add_to_cart')&&<Button className="assistant-add-all" onClick={()=>addAll(actions)} disabled={actions.some(action=>!isCurrent(action))||actions.every(action=>actionStates[actionKey(action)]==='added')}>Добавить всё в корзину</Button>}{(selection?.items.some(item=>item.status==='added')||actions.some(action=>actionStates[actionKey(action)]==='added'))&&<Link className="assistant-cart-link" to="/cart" onClick={()=>setOpen(false)}>Перейти в корзину →</Link>}</section>}<form onSubmit={event=>{event.preventDefault();send()}}><input aria-label="Сообщение помощнику" maxLength={1500} value={input} onChange={event=>setInput(event.target.value)} placeholder="Опишите задачу…"/><Button loading={false} disabled={!input.trim()} aria-label="Отправить"><Send/></Button></form></section>}</div>
}
