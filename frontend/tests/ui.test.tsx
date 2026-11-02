import{render,screen,fireEvent,waitFor}from'@testing-library/react'
import{MemoryRouter}from'react-router-dom'
import{describe,it,expect,beforeEach,vi}from'vitest'
import{CartProvider,useCart}from'../src/contexts/CartContext'
import{ToastProvider,useToast}from'../src/contexts/ToastContext'
import{AssistantChat}from'../src/components/AssistantChat'
import{MarkdownMessage}from'../src/components/MarkdownMessage'
import{Button,Modal,StatusBadge}from'../src/components/UI'
import{ServiceCard}from'../src/components/ServiceCard'

const service={id:1,slug:'test',name:'Тестовая услуга',category:'Тест',short_description:'Описание',description:'Описание услуги',stages:'Этап',unit:'м²',base_price_rub:'100.00',is_active:true,sort_order:1}

function CartHarness(){const{items,add,addMany,setQuantity}=useCart();return <><button onClick={()=>add(service,2)}>add</button><button onClick={()=>addMany([{service,quantity:3},{service:{...service,id:2,name:'Вторая услуга'},quantity:4}])}>many-cart</button><button onClick={()=>setQuantity(1,5)}>change</button><span data-testid="cart-quantity">{items[0]?.quantity||0}</span><span data-testid="cart-count">{items.length}</span></>}
function ToastHarness(){const{notify}=useToast();return <><button onClick={()=>notify({type:'success',title:'Готово'})}>same</button><button onClick={()=>['Один','Два','Три','Четыре'].forEach(title=>notify({type:'info',title}))}>many</button></>}

describe('UI feedback',()=>{
  beforeEach(()=>localStorage.clear())
  it('adds and updates a cart item',()=>{render(<MemoryRouter><CartProvider><CartHarness/></CartProvider></MemoryRouter>);fireEvent.click(screen.getByText('add'));expect(screen.getByText('2')).toBeInTheDocument();fireEvent.click(screen.getByText('change'));expect(screen.getByText('5')).toBeInTheDocument()})
  it('renders a localized status',()=>{render(<StatusBadge status="in_progress"/>);expect(screen.getByText('В работе')).toBeInTheDocument()})
  it('shows loading state and blocks repeated button clicks',()=>{render(<Button loading loadingText="Сохранение…">Сохранить</Button>);const button=screen.getByRole('button',{name:'Сохранение…'});expect(button).toBeDisabled();expect(button).toHaveAttribute('aria-busy','true')})
  it('deduplicates equal toasts',()=>{render(<ToastProvider><ToastHarness/></ToastProvider>);fireEvent.click(screen.getByText('same'));fireEvent.click(screen.getByText('same'));expect(screen.getAllByText('Готово')).toHaveLength(1)})
  it('keeps no more than three visible toasts',()=>{render(<ToastProvider><ToastHarness/></ToastProvider>);fireEvent.click(screen.getByText('many'));expect(screen.queryByText('Один')).not.toBeInTheDocument();expect(screen.getAllByRole('status')).toHaveLength(3)})
  it('announces a catalog addition and distinguishes an update',()=>{render(<MemoryRouter><ToastProvider><CartProvider><ServiceCard service={service}/></CartProvider></ToastProvider></MemoryRouter>);const add=screen.getByRole('button',{name:'Добавить Тестовая услуга'});fireEvent.click(add);expect(screen.getByText('Добавлено в корзину')).toBeInTheDocument();fireEvent.click(add);expect(screen.getByText('Количество обновлено')).toBeInTheDocument()})
  it('renders an accessible confirmation modal',()=>{render(<Modal title="Очистить корзину?" onClose={()=>{}}><p>Подтверждение</p></Modal>);expect(screen.getByRole('dialog',{name:'Очистить корзину?'})).toBeInTheDocument()})
  it('renders GFM markdown and blocks unsafe HTML and links',()=>{const{container}=render(<MarkdownMessage>{'# Заголовок\n\n**Жирный текст**\n\n- Один\n- Два\n\n[опасно](javascript:alert(1))\n\n<script>alert(2)</script>'}</MarkdownMessage>);expect(screen.getByRole('heading',{name:'Заголовок'})).toBeInTheDocument();expect(screen.getByText('Жирный текст').tagName).toBe('STRONG');expect(screen.getAllByRole('listitem')).toHaveLength(2);expect(screen.getByText('опасно').closest('a')).toBeNull();expect(container.querySelector('script')).toBeNull()})
  it('adds multiple cart entries atomically, merges duplicates and persists them',async()=>{render(<MemoryRouter><CartProvider><CartHarness/></CartProvider></MemoryRouter>);fireEvent.click(screen.getByText('add'));fireEvent.click(screen.getByText('many-cart'));expect(screen.getByTestId('cart-quantity')).toHaveTextContent('5');expect(screen.getByTestId('cart-count')).toHaveTextContent('2');await waitFor(()=>expect(JSON.parse(localStorage.getItem('sk-cart')||'[]')).toHaveLength(2))})
  it('adds the server-verified assistant quantity to the existing cart',async()=>{vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request)=>{const url=String(input);if(url.endsWith('/assistant/chat'))return new Response(JSON.stringify({answer:'### Укладка плитки\n\n**Расчёт готов**',mode:'demo',cart_actions:[{action:'add_to_cart',service_id:1,name:service.name,unit:'м²',quantity:'24.00',unit_price_rub:'100.00',line_total_rub:'2400.00'}]}),{status:200,headers:{'Content-Type':'application/json'}});if(url.endsWith('/services'))return new Response(JSON.stringify([service]),{status:200,headers:{'Content-Type':'application/json'}});return new Response('{}',{status:404})}));render(<MemoryRouter><ToastProvider><CartProvider><AssistantChat/><CartHarness/></CartProvider></ToastProvider></MemoryRouter>);fireEvent.click(screen.getByRole('button',{name:'Открыть ИИ-помощника'}));fireEvent.change(screen.getByLabelText('Сообщение помощнику'),{target:{value:'Рассчитай 24 м²'}});fireEvent.click(screen.getByRole('button',{name:'Отправить'}));expect(await screen.findByRole('heading',{name:'Укладка плитки'})).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:/Добавить — 24.00 м²/}));await waitFor(()=>expect(screen.getByTestId('cart-quantity')).toHaveTextContent('24'));expect(screen.getByRole('button',{name:/Готово/})).toBeDisabled();expect(screen.getByText('Перейти в корзину →')).toBeInTheDocument();vi.unstubAllGlobals()})
  it('sends the verified conversation context and cart preference on follow-up',async()=>{
    const requests:Array<Record<string,unknown>>=[]
    let assistantCalls=0
    vi.stubGlobal('fetch',vi.fn(async(input:string|URL|Request,init?:RequestInit)=>{
      const url=String(input)
      if(url.endsWith('/assistant/chat')){
        requests.push(JSON.parse(String(init?.body)))
        assistantCalls+=1
        const data=assistantCalls===1?{answer:'Расчёт потолка',mode:'demo',cart_actions:[{action:'add_to_cart',service_id:1,name:service.name,unit:'м²',quantity:'50.00',unit_price_rub:'100.00',line_total_rub:'5000.00',note:'Цвет: красный — пожелание клиента'}]}:{answer:'Перейдите к оформлению',mode:'demo',cart_actions:[],navigate_to:'/cart'}
        return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}})
      }
      if(url.endsWith('/services'))return new Response(JSON.stringify([service]),{status:200,headers:{'Content-Type':'application/json'}})
      return new Response('{}',{status:404})
    }))
    render(<MemoryRouter><ToastProvider><CartProvider><AssistantChat/><CartHarness/></CartProvider></ToastProvider></MemoryRouter>)
    fireEvent.click(screen.getByRole('button',{name:'Открыть ИИ-помощника'}))
    const input=screen.getByLabelText('Сообщение помощнику')
    fireEvent.change(input,{target:{value:'Натяжной потолок красного цвета 50 м²'}})
    fireEvent.click(screen.getByRole('button',{name:'Отправить'}))
    fireEvent.click(await screen.findByRole('button',{name:/Добавить — 50.00 м²/}))
    await waitFor(()=>expect(screen.getByTestId('cart-quantity')).toHaveTextContent('50'))
    fireEvent.change(input,{target:{value:'Что дальше?'}})
    fireEvent.click(screen.getByRole('button',{name:'Отправить'}))
    await waitFor(()=>expect(requests).toHaveLength(2))
    expect(requests[1].context_actions).toEqual([expect.objectContaining({service_id:1,quantity:'50.00',note:expect.stringContaining('красный')})])
    expect(requests[1].cart).toEqual([expect.objectContaining({service_id:1,quantity:50,note:expect.stringContaining('красный')})])
    expect(await screen.findByText('Перейдите к оформлению')).toBeInTheDocument()
    vi.unstubAllGlobals()
  })
})
