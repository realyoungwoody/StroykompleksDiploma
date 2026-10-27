import type{ButtonHTMLAttributes,InputHTMLAttributes,TextareaHTMLAttributes}from'react'
import{LoaderCircle,TriangleAlert,PackageOpen}from'lucide-react'
import type{Status}from'../types'
export function Button({className='',...props}:ButtonHTMLAttributes<HTMLButtonElement>){return <button className={`button ${className}`} {...props}/>}export function Input(props:InputHTMLAttributes<HTMLInputElement>){return <input className="input" {...props}/>}export function Textarea(props:TextareaHTMLAttributes<HTMLTextAreaElement>){return <textarea className="input textarea" {...props}/>}export function Spinner(){return <div className="state"><LoaderCircle className="spin"/><span>Загрузка…</span></div>}export function ErrorState({message}:{message:string}){return <div className="state error"><TriangleAlert/><span>{message}</span></div>}export function EmptyState({message}:{message:string}){return <div className="state"><PackageOpen/><span>{message}</span></div>}
export const statusLabel:Record<Status,string>={new:'Новая',contacted:'Связались с клиентом',in_progress:'В работе',completed:'Завершена',cancelled:'Отменена'}
export function StatusBadge({status}:{status:Status}){return <span className={`badge badge-${status}`}>{statusLabel[status]}</span>}
export const rub=(value:string|number)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2}).format(Number(value))
export const dateTime=(value:string)=>new Intl.DateTimeFormat('ru-RU',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Moscow'}).format(new Date(value))

