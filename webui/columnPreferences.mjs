/** Program-owned preferences, not browser storage. Load once before constructing
 * tables; only explicit reorder/reset gestures enqueue writes. Different tables
 * merge on the server, while changes to the same table use last-write-wins.
 */
export function createColumnPreferences(request) {
  let orders=new Map(),error='',tail=Promise.resolve();
  function save(table,order) {
    const body={table,order:order===null?null:[...order]};
    // Preserve rapid move/reset order, even when an earlier save failed.
    const pending=tail.then(async()=>{
      const result=await request(body);
      // A recreated view must never mistake an unsaved draft for disk state.
      // The active controller independently keeps its layout and error label.
      if(body.order===null)orders.delete(table);else orders.set(table,[...body.order]);
      return result;
    });
    tail=pending.catch(()=>{});
    return pending;
  }
  return {
    async load() {
      try {
        const data=await request();
        const values=data?.columnOrders;
        if(data?.version!==1 || !values || typeof values!=='object' || Array.isArray(values) ||
          Object.values(values).some(order=>!Array.isArray(order)||order.some(key=>typeof key!=='string')))
          throw Error('列顺序配置格式不兼容');
        orders=new Map(Object.entries(values).map(([table,order])=>[table,[...order]]));
        error='';return true;
      } catch(reason) {error=reason.message||String(reason);return false;}
    },
    get(table) {const order=orders.get(table);return order?[...order]:null;},
    get error() {return error;},
    set:(table,order)=>save(table,order),
    remove:table=>save(table,null),
  };
}

async function request(body) {
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),5000);
  try {
    const response=await fetch('/api/ui/column-order',{
      method:body?'POST':'GET',cache:'no-store',signal:controller.signal,
      ...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{}),
    });
    const value=await response.json();
    if(!response.ok || value?.error)throw Error(value?.error||`请求失败 ${response.status}`);
    return value;
  } finally {clearTimeout(timeout);}
}
export const columnPreferences=createColumnPreferences(request);
export const initializeColumnPreferences=()=>columnPreferences.load();
