import {createContext,useCallback,useContext,useEffect,useMemo,useRef,useState,type ReactNode} from 'react'
import {CheckCircle2,CircleAlert,Info,TriangleAlert,X} from 'lucide-react'

export type ToastKind='success'|'error'|'warning'|'info'
export type ToastInput={type:ToastKind;title:string;description?:string;duration?:number}
type Toast=ToastInput&{id:number}
type ToastValue={notify:(toast:ToastInput)=>number;dismiss:(id:number)=>void}

const ToastContext=createContext<ToastValue|null>(null)
const icons={success:CheckCircle2,error:CircleAlert,warning:TriangleAlert,info:Info}

export function ToastProvider({children}:{children:ReactNode}){
  const[toasts,setToasts]=useState<Toast[]>([])
  const nextId=useRef(1)
  const dismiss=useCallback((id:number)=>setToasts(current=>current.filter(toast=>toast.id!==id)),[])
  const notify=useCallback((input:ToastInput)=>{
    let createdId=0
    setToasts(current=>{
      const duplicate=current.find(toast=>toast.type===input.type&&toast.title===input.title&&toast.description===input.description)
      if(duplicate){createdId=duplicate.id;return current}
      createdId=nextId.current++
      return[...current,{...input,id:createdId}].slice(-3)
    })
    return createdId
  },[])
  const value=useMemo(()=>({notify,dismiss}),[notify,dismiss])
  return <ToastContext.Provider value={value}>{children}<div className="toast-viewport" aria-live="polite" aria-label="Уведомления">{toasts.map(toast=><ToastItem key={toast.id} toast={toast} dismiss={dismiss}/>)}</div></ToastContext.Provider>
}

function ToastItem({toast,dismiss}:{toast:Toast;dismiss:(id:number)=>void}){
  const Icon=icons[toast.type]
  useEffect(()=>{const timer=window.setTimeout(()=>dismiss(toast.id),toast.duration??(toast.type==='error'?6500:4200));return()=>window.clearTimeout(timer)},[toast,dismiss])
  return <div className={`toast toast-${toast.type}`} role={toast.type==='error'?'alert':'status'}>
    <Icon className="toast-icon" aria-hidden="true"/>
    <div><strong>{toast.title}</strong>{toast.description&&<p>{toast.description}</p>}</div>
    <button type="button" onClick={()=>dismiss(toast.id)} aria-label="Закрыть уведомление"><X/></button>
  </div>
}

export function useToast(){const value=useContext(ToastContext);if(!value)throw new Error('ToastProvider missing');return value}
