/** Browser presentation preference only. Keys, never labels or game values,
 * survive renamed/hidden fields. Missing/new columns retain their default order.
 * An injected program preference store handles persistence, independently of
 * the renderer. A failed save keeps the local layout with an explicit warning.
 */
export function createColumnOrder(id, store) {
  let saved=[],persisted=true,error='',generation=0,settled=Promise.resolve(true);
  try {
    const value=id && store ? store.get(id) : null;
    if(Array.isArray(value)) saved=[...new Set(value.filter(key=>typeof key==='string'))];
  } catch { /* A damaged or denied preference must never block live data. */ }
  function arrange(columns) {
    const byKey=new Map(columns.map(column=>[column.key,column]));
    const result=[];
    for(const key of saved) if(byKey.has(key)){result.push(byKey.get(key));byKey.delete(key);}
    return result.concat([...byKey.values()]);
  }
  function persist(reset=false) {
    persisted=false;error='';const current=++generation;
    const success=()=>{if(current===generation)persisted=true;return true;};
    const failure=reason=>{if(current===generation)error=reason.message||String(reason);return false;};
    try {
      if(!id || !store)throw Error('该表未配置持久化存储');
      const pending=reset?store.remove(id):store.set(id,[...saved]);
      settled=pending?.then ? Promise.resolve(pending).then(success,failure) : Promise.resolve(success());
    } catch(reason) {settled=Promise.resolve(failure(reason));}
  }
  return {arrange,get persisted(){return persisted;},get error(){return error;},get settled(){return settled;},get customized(){return saved.length>0;},
    move(columns,source,target,side='before') {
      if(source===target || !['before','after'].includes(side) ||
        !columns.some(column=>column.key===source) || !columns.some(column=>column.key===target))return false;
      // Keep hidden keys while moving the visible source next to its target.
      const known=new Set(saved),order=[...saved,...columns.filter(column=>!known.has(column.key)).map(column=>column.key)];
      order.splice(order.indexOf(source),1);
      order.splice(order.indexOf(target)+(side==='after'?1:0),0,source);
      saved=order;persist();return true;
    },
    reset(){saved=[];persist(true);},
  };
}
