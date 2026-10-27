export type Service={id:number;slug:string;name:string;category:string;short_description:string;description:string;stages:string;unit:string;base_price_rub:string;is_active:boolean;sort_order:number}
export type CartItem={service:Service;quantity:number}
export type Quote={items:Array<{service_id:number;name:string;unit:string;quantity:string;unit_price_rub:string;line_total_rub:string}>;estimated_total_rub:string;currency:string;warning:string}
export type Order={id:number;public_number:string;customer_name:string;phone:string;email?:string;object_location?:string;desired_date?:string;comment?:string;status:Status;estimated_total_rub:string;admin_note?:string;created_at:string;updated_at:string;items:Array<{service_id:number;service_name_snapshot:string;unit_snapshot:string;quantity:string;unit_price_snapshot:string;line_total_rub:string}>;history:Array<{old_status?:string;new_status:Status;created_at:string}>}
export type Status='new'|'contacted'|'in_progress'|'completed'|'cancelled'

