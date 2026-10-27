const API='/api/v1'
export class ApiError extends Error{status:number;constructor(status:number,message:string){super(message);this.status=status}}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{const res=await fetch(`${API}${path}`,{credentials:'include',...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});const data=await res.json().catch(()=>({}));if(!res.ok){const validation=Array.isArray(data?.detail)?data.detail.map((item:{msg?:string})=>item.msg).filter(Boolean).join('; '):'';throw new ApiError(res.status,data?.error?.message||validation||'Не удалось выполнить запрос')}return data as T}

