import{render,screen,fireEvent}from'@testing-library/react'
import{MemoryRouter}from'react-router-dom'
import{describe,it,expect,beforeEach}from'vitest'
import{CartProvider,useCart}from'../src/contexts/CartContext'
import{ToastProvider,useToast}from'../src/contexts/ToastContext'
import{Button,Modal,StatusBadge}from'../src/components/UI'
import{ServiceCard}from'../src/components/ServiceCard'

const service={id:1,slug:'test',name:'Тестовая услуга',category:'Тест',short_description:'Описание',description:'Описание услуги',stages:'Этап',unit:'м²',base_price_rub:'100.00',is_active:true,sort_order:1}

function CartHarness(){const{items,add,setQuantity}=useCart();return <><button onClick={()=>add(service,2)}>add</button><button onClick={()=>setQuantity(1,5)}>change</button><span>{items[0]?.quantity||0}</span></>}
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
})
