import{useEffect,useRef,useState,type FormEvent}from'react'
import{Link,useNavigate,useParams}from'react-router-dom'
import{ArrowRight,CheckCircle2,ClipboardCheck,Layers3,LoaderCircle,Search,ShieldCheck,Sparkles,Trash2}from'lucide-react'
import{api}from'../api/client'
import{useCart}from'../contexts/CartContext'
import{useToast}from'../contexts/ToastContext'
import type{Quote,Service,Status}from'../types'
import{Button,dateTime,EmptyState,ErrorState,FieldError,Input,Modal,rub,Spinner,StatusBadge,Textarea}from'../components/UI'
import{ServiceCard}from'../components/ServiceCard'

function useServices(){
  const[data,setData]=useState<Service[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState('')
  useEffect(()=>{api<Service[]>('/services').then(setData).catch(e=>setError(e.message)).finally(()=>setLoading(false))},[])
  return{data,loading,error}
}

export function Home(){
  const{data,loading}=useServices()
  const[faq,setFaq]=useState<Array<{question:string;answer:string}>>([])
  useEffect(()=>{api<typeof faq>('/faq').then(setFaq).catch(()=>{})},[])
  return <>
    <section className="hero"><div className="container hero-grid"><div><span className="kicker">Цифровой сервис • Нижний Новгород</span><h1>Строительные и отделочные работы с понятным процессом оформления заявки</h1><p>Выберите необходимые услуги, получите предварительный расчёт стоимости и отправьте структурированную заявку на рассмотрение.</p><div className="hero-actions"><Link className="button" to="/services">Выбрать услуги <ArrowRight/></Link><a className="button ghost" href="#process">Как это работает</a></div><div className="hero-note"><ShieldCheck/> Учебная демонстрационная система. Без платежей и коммерческих обязательств.</div></div><div className="blueprint" aria-label="Схематичная иллюстрация помещения"><div className="plan"><span className="room r1">01<small>подготовка</small></span><span className="room r2">02<small>расчёт</small></span><span className="room r3">03<small>заявка</small></span><span className="measure">19 200 ₽<small>пример расчёта</small></span></div></div></div></section>
    <section className="section"><div className="container"><div className="section-head"><div><span className="eyebrow">Каталог</span><h2>Популярные направления работ</h2></div><Link className="text-link" to="/services">Все услуги <ArrowRight/></Link></div>{loading?<Spinner/>:<div className="service-grid">{data.slice(0,4).map(s=><ServiceCard key={s.id} service={s}/>)}</div>}</div></section>
    <section id="process" className="section process"><div className="container"><span className="eyebrow">Стандартизированный процесс</span><h2>От выбора до контроля статуса — четыре шага</h2><div className="steps">{[['01','Выберите услуги','Найдите работы в каталоге и укажите объём.'],['02','Получите расчёт','Backend рассчитает стоимость по актуальным ценам.'],['03','Отправьте заявку','Контактные данные и позиции сохранятся в системе.'],['04','Следите за статусом','Проверяйте этап обработки по номеру и телефону.']].map(x=><article key={x[0]}><b>{x[0]}</b><h3>{x[1]}</h3><p>{x[2]}</p></article>)}</div></div></section>
    <section className="section benefits"><div className="container"><div className="benefit-title"><span className="kicker">Lean-подход</span><h2>Меньше ручных действий. Больше прозрачности.</h2><p>Единая структура обращения снижает повторный ввод, а визуальные статусы помогают не терять заявки.</p></div><div className="benefit-grid">{[[Layers3,'Структурированные данные'],[ClipboardCheck,'Контроль статуса'],[Sparkles,'Типовые консультации']].map(([Icon,title])=><article key={String(title)}><Icon/><b>{String(title)}</b><p>Информация доступна в одном понятном цифровом процессе.</p></article>)}</div></div></section>
    <section className="section"><div className="container narrow"><span className="eyebrow">FAQ</span><h2>Частые вопросы</h2><div className="faq">{faq.slice(0,10).map((f,i)=><details key={f.question} open={i===0}><summary>{f.question}<span>+</span></summary><p>{f.answer}</p></details>)}</div></div></section>
  </>
}

export function Services(){
  const{data,loading,error}=useServices()
  const[search,setSearch]=useState(''),[category,setCategory]=useState('Все')
  const categories=['Все',...new Set(data.map(s=>s.category))]
  const filtered=data.filter(s=>(category==='Все'||s.category===category)&&s.name.toLowerCase().includes(search.toLowerCase()))
  return <section className="page"><div className="container"><div className="page-title"><span className="eyebrow">8 направлений</span><h1>Каталог услуг</h1><p>Все цены демонстрационные и служат для предварительного расчёта.</p></div><div className="filters"><label><Search/><Input aria-label="Поиск услуг" placeholder="Найти услугу" value={search} onChange={e=>setSearch(e.target.value)}/></label><select aria-label="Категория" value={category} onChange={e=>setCategory(e.target.value)}>{categories.map(c=><option key={c}>{c}</option>)}</select></div>{loading?<Spinner/>:error?<ErrorState message={error}/>:filtered.length?<div className="service-grid">{filtered.map(s=><ServiceCard key={s.id} service={s}/>)}</div>:<EmptyState message="По вашему запросу услуг не найдено"/>}</div></section>
}

export function ServiceDetail(){
  const{slug}=useParams()
  const[service,setService]=useState<Service|null>(null),[error,setError]=useState(''),[quantity,setQuantity]=useState(10)
  const{add}=useCart(),{notify}=useToast()
  useEffect(()=>{api<Service>(`/services/${slug}`).then(setService).catch(e=>setError(e.message))},[slug])
  if(error)return <section className="page container"><ErrorState message={error}/></section>
  if(!service)return <section className="page container"><Spinner/></section>
  const quantityError=!Number.isFinite(quantity)||quantity<.1||quantity>10000?'Укажите объём от 0,1 до 10 000.':''
  const handleAdd=()=>{if(quantityError)return;const result=add(service,quantity);notify({type:'success',title:result==='updated'?'Количество обновлено':'Добавлено в корзину',description:`${service.name} — ${quantity} ${service.unit}`})}
  return <section className="page"><div className="container detail-grid"><div className={`detail-art art-${service.id%5}`}><span>{service.category}</span><strong>{service.name.split(' ').slice(0,2).join(' ')}</strong></div><div><Link className="back" to="/services">← Каталог</Link><span className="eyebrow">{service.category}</span><h1>{service.name}</h1><p className="lead">{service.description}</p><h3>Этапы работ</h3><ol className="stage-list">{service.stages.split(';').map(x=><li key={x}>{x}</li>)}</ol><div className="estimator"><div><span>Цена за {service.unit}</span><b>{rub(service.base_price_rub)}</b></div><label>Объём, {service.unit}<Input type="number" min="0.1" max="10000" step="0.1" value={Number.isNaN(quantity)?'':quantity} aria-invalid={!!quantityError} aria-describedby={quantityError?'quantity-error':undefined} onChange={e=>setQuantity(e.target.value===''?Number.NaN:Number(e.target.value))}/>{quantityError&&<FieldError id="quantity-error">{quantityError}</FieldError>}</label><div className="estimate-total"><span>Предварительно</span><b aria-live="polite">{quantityError?'—':rub(Number(service.base_price_rub)*quantity)}</b></div><Button disabled={!!quantityError} onClick={handleAdd}>Добавить в корзину</Button><small>Стоимость ориентировочная и может измениться после уточнения объёма и условий работ.</small></div></div></div></section>
}

export function Cart(){
  const{items,setQuantity,remove,clear}=useCart()
  const{notify}=useToast()
  const[quote,setQuote]=useState<Quote|null>(null),[error,setError]=useState(''),[recalculating,setRecalculating]=useState(false),[confirmClear,setConfirmClear]=useState(false)
  useEffect(()=>{
    if(!items.length){setQuote(null);setError('');setRecalculating(false);return}
    const controller=new AbortController()
    setRecalculating(true);setError('')
    api<Quote>('/quotes',{method:'POST',signal:controller.signal,body:JSON.stringify({items:items.map(i=>({service_id:i.service.id,quantity:String(i.quantity)}))})}).then(setQuote).catch(e=>{if(e.name!=='AbortError'){setError(e.message);notify({type:'error',title:'Не удалось пересчитать корзину',description:e.message})}}).finally(()=>{if(!controller.signal.aborted)setRecalculating(false)})
    return()=>controller.abort()
  },[items,notify])
  if(!items.length)return <section className="page container"><div className="page-title"><h1>Корзина услуг</h1></div><EmptyState message="В корзине пока нет услуг"/><div className="center"><Link className="button" to="/services">Перейти в каталог</Link></div></section>
  const deleteItem=(id:number,name:string)=>{remove(id);notify({type:'info',title:'Позиция удалена',description:name})}
  const clearCart=()=>{clear();setConfirmClear(false);notify({type:'info',title:'Корзина очищена'})}
  return <section className="page"><div className="container narrow-wide"><div className="page-title row"><div><span className="eyebrow">Предварительный расчёт</span><h1>Корзина услуг</h1></div><Button className="ghost danger" onClick={()=>setConfirmClear(true)}><Trash2/> Очистить</Button></div>{error&&<ErrorState message={error}/>}<div className="cart-list" aria-busy={recalculating}>{items.map(i=>{const line=quote?.items.find(x=>x.service_id===i.service.id);return <article key={i.service.id}><div><b>{i.service.name}</b><span>{rub(line?.unit_price_rub||i.service.base_price_rub)} / {i.service.unit}</span></div><label>Объём<Input type="number" min=".1" max="10000" step=".1" value={i.quantity} onChange={e=>setQuantity(i.service.id,Math.min(10000,Math.max(.1,Number(e.target.value)||.1)))}/></label><strong>{rub(line?.line_total_rub||Number(i.service.base_price_rub)*i.quantity)}</strong><button className="icon-button" onClick={()=>deleteItem(i.service.id,i.service.name)} aria-label={`Удалить ${i.service.name}`}><Trash2/></button></article>})}</div><div className="cart-total"><div><span>Предварительная стоимость</span><b>{quote?rub(quote.estimated_total_rub):'Расчёт…'}</b><small>{recalculating&&<span className="recalculating"><LoaderCircle className="spin"/> Пересчитываем стоимость…</span>}{!recalculating&&quote?.warning}</small></div><Link className={`button${recalculating?' disabled-link':''}`} aria-disabled={recalculating} onClick={e=>{if(recalculating)e.preventDefault()}} to="/request">Перейти к оформлению <ArrowRight/></Link></div></div>{confirmClear&&<Modal title="Очистить корзину?" onClose={()=>setConfirmClear(false)}><p>Все выбранные услуги и объёмы будут удалены.</p><div className="modal-actions"><Button className="ghost" onClick={()=>setConfirmClear(false)}>Отмена</Button><Button className="danger-solid" onClick={clearCart}>Очистить корзину</Button></div></Modal>}</section>
}

type FormErrors={name?:string;phone?:string;email?:string;consent?:string}
export function RequestPage(){
  const{items,clear}=useCart(),navigate=useNavigate(),{notify}=useToast()
  const[loading,setLoading]=useState(false),[error,setError]=useState(''),[quote,setQuote]=useState<Quote|null>(null),[errors,setErrors]=useState<FormErrors>({})
  const idempotencyKey=useRef(globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`)
  useEffect(()=>{if(items.length)api<Quote>('/quotes',{method:'POST',body:JSON.stringify({items:items.map(i=>({service_id:i.service.id,quantity:String(i.quantity)}))})}).then(setQuote).catch(e=>setError(e.message))},[items])
  if(!items.length)return <section className="page container"><EmptyState message="Добавьте услуги перед оформлением"/><div className="center"><Link className="button" to="/services">Каталог</Link></div></section>
  async function submit(e:FormEvent<HTMLFormElement>){
    e.preventDefault();if(loading)return
    const fd=new FormData(e.currentTarget),name=String(fd.get('name')||'').trim(),phone=String(fd.get('phone')||'').trim(),email=String(fd.get('email')||'').trim()
    const next:FormErrors={}
    if(name.length<2)next.name='Введите имя — не менее 2 символов.'
    if(phone.replace(/\D/g,'').length<10)next.phone='Введите телефон — не менее 10 цифр.'
    if(email&&!/^\S+@\S+\.\S+$/.test(email))next.email='Проверьте формат email.'
    if(fd.get('consent')!=='on')next.consent='Подтвердите согласие для отправки заявки.'
    setErrors(next);if(Object.keys(next).length)return
    setLoading(true);setError('')
    try{
      const result=await api<{public_number:string}>('/orders',{method:'POST',headers:{'Idempotency-Key':idempotencyKey.current},body:JSON.stringify({customer_name:name,phone,email:email||null,object_location:fd.get('location')||null,desired_date:fd.get('date')||null,comment:fd.get('comment')||null,consent_accepted:true,items:items.map(i=>({service_id:i.service.id,quantity:String(i.quantity)}))})})
      clear();navigate(`/request/success/${result.public_number}`)
    }catch(e){const message=e instanceof Error?e.message:'Не удалось отправить заявку';setError(message);notify({type:'error',title:'Заявка не отправлена',description:message})}finally{setLoading(false)}
  }
  return <section className="page"><div className="container form-layout"><form className="form-card" onSubmit={submit} noValidate aria-busy={loading}><span className="eyebrow">Оформление</span><h1>Контактные данные</h1><div className="notice"><ShieldCheck/>Учебный проект: данные и заявка не передаются реальному предприятию. Используйте только тестовые сведения.</div>{error&&<ErrorState message={error}/>}<label>Имя заказчика *<Input name="name" maxLength={120} aria-invalid={!!errors.name} aria-describedby={errors.name?'name-error':undefined} onChange={()=>setErrors(v=>({...v,name:undefined}))}/>{errors.name&&<FieldError id="name-error">{errors.name}</FieldError>}</label><label>Телефон *<Input name="phone" placeholder="+7 000 000-00-01" aria-invalid={!!errors.phone} aria-describedby={errors.phone?'phone-error':undefined} onChange={()=>setErrors(v=>({...v,phone:undefined}))}/>{errors.phone&&<FieldError id="phone-error">{errors.phone}</FieldError>}</label><div className="form-row"><label>Email<Input name="email" type="email" maxLength={254} aria-invalid={!!errors.email} aria-describedby={errors.email?'email-error':undefined} onChange={()=>setErrors(v=>({...v,email:undefined}))}/>{errors.email&&<FieldError id="email-error">{errors.email}</FieldError>}</label><label>Желаемая дата<Input name="date" type="date"/></label></div><label>Район или местоположение<Input name="location" maxLength={250}/></label><label>Комментарий<Textarea name="comment" maxLength={2000} rows={4}/></label><label className="check"><input name="consent" type="checkbox" aria-invalid={!!errors.consent} aria-describedby={errors.consent?'consent-error':undefined} onChange={()=>setErrors(v=>({...v,consent:undefined}))}/> Согласен на использование введённых тестовых данных в демонстрационной системе.</label>{errors.consent&&<FieldError id="consent-error">{errors.consent}</FieldError>}<Button loading={loading} loadingText="Отправка заявки…">Отправить заявку</Button></form><aside className="order-summary"><h2>Ваша заявка</h2>{items.map(i=><div key={i.service.id}><span>{i.service.name}<small>{i.quantity} {i.service.unit}</small></span><b>{rub(Number(i.service.base_price_rub)*i.quantity)}</b></div>)}<hr/><div><strong>Предварительно</strong><strong>{quote?rub(quote.estimated_total_rub):'…'}</strong></div><p>Сумма будет пересчитана сервером по актуальным ценам при отправке.</p></aside></div></section>
}

export function Success(){const{number}=useParams();return <section className="page"><div className="container success"><CheckCircle2/><span className="eyebrow">Заявка зарегистрирована</span><h1>Заявка успешно отправлена</h1><p>Сохраните номер — он понадобится вместе с телефоном для проверки статуса.</p><div className="order-number">{number}</div><StatusBadge status="new"/><div className="hero-actions"><Link className="button" to={`/track?number=${number}`}>Проверить статус</Link><Link className="button ghost" to="/">На главную</Link></div></div></section>}

export function Track(){
  const params=new URLSearchParams(location.search)
  const[number,setNumber]=useState(params.get('number')||''),[phone,setPhone]=useState(''),[result,setResult]=useState<{public_number:string;status:Status;estimated_total_rub:string;created_at:string;updated_at:string;items:Array<{service_name_snapshot:string;quantity:string;unit_snapshot:string;line_total_rub:string}>}|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false)
  async function submit(e:FormEvent){e.preventDefault();if(loading)return;setLoading(true);setError('');setResult(null);try{setResult(await api('/orders/track',{method:'POST',body:JSON.stringify({public_number:number.toUpperCase(),phone})}))}catch(e){setError(e instanceof Error?e.message:'Ошибка поиска')}finally{setLoading(false)}}
  return <section className="page"><div className="container track-grid"><form className="form-card" onSubmit={submit} aria-busy={loading}><span className="eyebrow">Без регистрации</span><h1>Проверить заявку</h1><p>Введите номер из подтверждения и тот же телефон, который был указан при оформлении.</p><label>Номер заявки<Input value={number} onChange={e=>setNumber(e.target.value)} placeholder="SC-XXXXXXXXXX" required/></label><label>Телефон<Input value={phone} onChange={e=>setPhone(e.target.value)} required/></label><Button loading={loading} loadingText="Поиск заявки…">Показать статус</Button>{error&&<ErrorState message={error}/>}</form>{result?<div className="track-result"><div className="row"><div><span className="eyebrow">{result.public_number}</span><h2>Состояние заявки</h2></div><StatusBadge status={result.status}/></div><p>Создана {dateTime(result.created_at)}</p>{result.items.map((i,n)=><div className="track-item" key={n}><span>{i.service_name_snapshot}<small>{i.quantity} {i.unit_snapshot}</small></span><b>{rub(i.line_total_rub)}</b></div>)}<div className="track-total"><span>Предварительная стоимость</span><b>{rub(result.estimated_total_rub)}</b></div></div>:<div className="track-placeholder"><Search/><h2>Статус защищён</h2><p>Одного номера недостаточно: система также проверяет телефон и не раскрывает чужие данные.</p></div>}</div></section>
}

export function About(){return <section className="page"><div className="container narrow"><span className="eyebrow">О проекте</span><h1>Цифровой поток обработки обращений</h1><p className="lead">MVP создан для выпускной квалификационной работы о повышении экономической эффективности на основе принципов бережливого производства.</p><div className="prose"><h2>Что меняется</h2><p>Вместо неструктурированного обращения клиент выбирает позиции из единого каталога, получает расчёт и передаёт данные в стандартном формате. Администратор видит очередь, историю и просроченные новые заявки.</p><h2>Что система не делает</h2><p>Это не официальный сайт, не CRM и не платёжная система. Здесь нет реальных сотрудников, оплаты, SMS, 1С и коммерческих обязательств.</p><h2>Оценка потенциального эффекта</h2><p>При условных 20 заявках и сокращении обработки с 15 до 5 минут сценарная экономия составит 200 минут — 3 часа 20 минут. Это иллюстрация на условных данных, а не результат производственного эксперимента.</p></div></div></section>}
export function NotFound(){return <section className="page container success"><span className="order-number">404</span><h1>Страница не найдена</h1><Link className="button" to="/">Вернуться на главную</Link></section>}
