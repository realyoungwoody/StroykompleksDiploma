import {createContext,useContext,useEffect,useMemo,useState,type ReactNode} from 'react'
import type{CartItem,Service}from'../types'
type CartValue={items:CartItem[];count:number;add:(s:Service,q?:number)=>void;setQuantity:(id:number,q:number)=>void;remove:(id:number)=>void;clear:()=>void}
const CartContext=createContext<CartValue|null>(null)
export function CartProvider({children}:{children:ReactNode}){const[items,setItems]=useState<CartItem[]>(()=>{try{return JSON.parse(localStorage.getItem('sk-cart')||'[]')}catch{return[]}});useEffect(()=>localStorage.setItem('sk-cart',JSON.stringify(items)),[items]);const value=useMemo(()=>({items,count:items.length,add:(service:Service,quantity=1)=>setItems(old=>{const found=old.find(x=>x.service.id===service.id);return found?old.map(x=>x.service.id===service.id?{...x,quantity:Math.min(10000,Math.round((x.quantity+quantity)*100)/100)}:x):[...old,{service,quantity}]}),setQuantity:(id:number,quantity:number)=>setItems(old=>old.map(x=>x.service.id===id?{...x,quantity}:x)),remove:(id:number)=>setItems(old=>old.filter(x=>x.service.id!==id)),clear:()=>setItems([])}),[items]);return <CartContext.Provider value={value}>{children}</CartContext.Provider>}
export function useCart(){const value=useContext(CartContext);if(!value)throw new Error('CartProvider missing');return value}

