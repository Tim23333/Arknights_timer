import {createColumnOrder} from './columnOrder.mjs';
import {columnPreferences} from './columnPreferences.mjs';

/** Column gestures for refreshing tables. No polling or data sorting:
 * explicit changes save only column keys through the program preference store.
 * Header handlers survive ordinary samples; schema changes cancel active drags.
 */
export function createTableColumnOrder(table,{key=table.id,changed,store=columnPreferences}={}) {
  const doc=table.ownerDocument;
  const state=createColumnOrder(key,store);
  const toolbar=doc.createElement('div');toolbar.className='table-column-tools';
  const hint=doc.createElement('span');hint.textContent='拖动表头调整列顺序';
  const reset=doc.createElement('button');reset.type='button';reset.textContent='恢复默认列顺序';
  const status=doc.createElement('span');status.className='column-order-status';status.setAttribute('role','status');
  if(store.error)status.textContent=`未能读取程序列顺序配置：${store.error}；暂用默认顺序`;
  toolbar.append(hint,reset,status);
  const scroll=table.parentElement;
  if(scroll?.matches('.table-scroll, .policy-scroll'))scroll.before(toolbar);
  else table.before(toolbar);
  let columns=[],dragKey=null,dropHeader=null,headerRow=null,headerSchema=null,reportGeneration=0;
  function clearDrag(){
    dragKey=null;dropHeader?.removeAttribute('data-column-drop');dropHeader=null;
    table.classList.remove('column-dragging');
  }
  async function report(text){
    const current=++reportGeneration;
    status.textContent=text+'，正在保存到程序配置…';
    await state.settled;
    if(current!==reportGeneration)return;
    status.textContent=text+(state.persisted?'，已保存到程序配置':`；未能确认保存：${state.error}，本页布局保留`);
  }
  function move(source,target,side){
    if(!state.move(columns,source,target,side))return;
    clearDrag();changed();reset.disabled=!state.customized;report('列顺序已调整');
    for(const button of table.tHead.querySelectorAll('.column-drag-label'))if(button.dataset.columnKey===source)button.focus({preventScroll:true});
  }
  reset.onclick=()=>{clearDrag();state.reset();changed();reset.disabled=true;report('已恢复默认列顺序');};
  function decorate(nextColumns){
    reset.disabled=!state.customized;
    const nextSchema=JSON.stringify(nextColumns.map(column=>[column.key,column.label]));
    if(headerRow===table.tHead.rows[0] && headerSchema===nextSchema)return;
    clearDrag();columns=nextColumns;headerRow=table.tHead.rows[0];headerSchema=nextSchema;
    for(const [index,column] of columns.entries()){
      const header=table.tHead.rows[0]?.cells[index];if(!header)continue;
      header.dataset.columnKey=column.key;
      let label=header.querySelector('.column-drag-label');
      if(!label){
        label=doc.createElement('button');label.type='button';label.className='column-drag-label';
        // Keep existing width-fit controls separate from the draggable label.
        for(const child of [...header.childNodes])if(child.nodeType===3)child.remove();
        header.prepend(label);
      }
      label.textContent=column.label;label.dataset.columnKey=column.key;label.draggable=true;
      label.title='拖动调整列顺序；也可按 Alt + 左右方向键移动';
      label.setAttribute('aria-label',`${column.label}：拖动排序，Alt 加左右键移动`);
      label.ondragstart=event=>{
        dragKey=column.key;event.dataTransfer.effectAllowed='move';
        event.dataTransfer.setData('text/plain',String(column.key));table.classList.add('column-dragging');
      };
      label.ondragend=clearDrag;
      header.ondragover=event=>{
        if(dragKey===null)return;
        event.preventDefault();event.dataTransfer.dropEffect='move';
        if(dropHeader!==header)dropHeader?.removeAttribute('data-column-drop');
        dropHeader=header;const bounds=header.getBoundingClientRect();
        header.dataset.columnDrop=event.clientX<bounds.left+bounds.width/2?'before':'after';
        const viewport=table.closest('.table-scroll, .policy-scroll');
        if(viewport){const box=viewport.getBoundingClientRect();
          if(event.clientX<box.left+32)viewport.scrollLeft-=24;
          else if(event.clientX>box.right-32)viewport.scrollLeft+=24;
        }
      };
      header.ondrop=event=>{
        if(dragKey===null)return;
        event.preventDefault();const bounds=header.getBoundingClientRect();
        move(dragKey,column.key,event.clientX<bounds.left+bounds.width/2?'before':'after');clearDrag();
      };
      label.onkeydown=event=>{
        if(event.key==='Escape'){clearDrag();return;}
        if(!event.altKey || !['ArrowLeft','ArrowRight'].includes(event.key))return;
        event.preventDefault();const delta=event.key==='ArrowLeft'?-1:1;
        const target=columns[index+delta];if(target)move(column.key,target.key,delta<0?'before':'after');
      };
    }
  }
  return {arrange:state.arrange,decorate};
}

/** For hand-built log/policy rows: reorder existing keyed DOM cells, preserving
 * switch handlers and values. Call after rebuilding rows in default order.
 */
export function createStaticTableColumnOrder(table,columns,key=table.id,{store}={}){
  const controller=createTableColumnOrder(table,{key,changed:apply,store});
  function apply(){
    const arranged=controller.arrange(columns);
    for(const row of table.rows){
      if(row.cells.length!==columns.length)continue; // Empty colspan row.
      [...row.cells].forEach((cell,index)=>{cell.dataset.columnKey ||= columns[index].key;});
      const cells=new Map([...row.cells].map(cell=>[cell.dataset.columnKey,cell]));
      arranged.forEach((column,index)=>{const cell=cells.get(column.key);if(row.cells[index]!==cell)row.insertBefore(cell,row.cells[index]||null);});
    }
    controller.decorate(arranged);
  }
  return {apply};
}
