import {createEntityDetailModel} from './entityDetailModel.mjs';
import {createTableRenderer} from './tableRenderer.mjs';
import {createPager} from './pagination.mjs';
import {formatClock} from './model.mjs';

/** One keyed, tabbed detail view; source/target ownership stays in app/detailSelection.
 * Only the active panel paints. Refreshes retain the tab, pager, scroll and DOM.
 * All source text goes through textContent, never interpreted game markup/HTML.
 */
export function createEntityDetails(kind,id,tabHost,{orderStore}={}) {
  const doc=tabHost.ownerDocument;
  const element=(tag,className,text)=>{
    const item=doc.createElement(tag); item.className=className;
    if (text!==undefined) item.textContent=text;
    return item;
  };
  const root=element('div','entity-details');
  const status=element('p','entity-detail-status');
  const frameLine=element('div','entity-detail-frames');
  const clockTime=element('strong','entity-detail-clock'), clockFrame=element('strong','');
  const basicFrame=element('strong',''), detailFrame=element('strong','');
  frameLine.append(element('span','','游戏时钟'),clockTime,element('span','','逻辑帧'),clockFrame,
    element('span','','已显示基础来源帧'),basicFrame,element('span','','已显示详情来源帧'),detailFrame);
  basicFrame.dataset.sourceDomain='basic';detailFrame.dataset.sourceDomain='detail';
  const hint=element('p','entity-detail-hint','详情与 PySide6 一样独立于主表隐藏列；采集开关及详情分组展示开关仍生效。“旧”不是当前帧；生效帧页为本地静态资料。');
  const panel=element('section','entity-detail-panel');
  root.append(status,frameLine,hint,panel);
  const model=createEntityDetailModel(kind,id), states=new Map(), panels=new Map();
  const prefix=`entity-detail-${kind}-${String(id).replace(/[^\w-]/g,'_')}`;
  let current='overview', view=null, buttons=[];
  tabHost.setAttribute('role','tablist'); tabHost.setAttribute('aria-label','实体详情分类');
  const set=(item,value)=>{if(item.textContent!==String(value)) item.textContent=String(value);};

  function draw() {
    if (!view) return;
    for (const button of buttons) {
      const selected=button.dataset.tab===current;
      button.classList.toggle('active',selected);
      if(button.getAttribute('aria-selected')!==String(selected)) button.setAttribute('aria-selected',String(selected));
      if(button.tabIndex!==(selected?0:-1)) button.tabIndex=selected?0:-1;
    }
    const tab=view.tabs.find(tab=>tab.id===current);
    for(const [key,body] of panels) if(body.hidden!==(key!==current)) body.hidden=key!==current;
    const activePanel=panels.get(current);
    let state=states.get(current);
    if (!state) {
      const body=element('div','entity-tab-content');
      const note=element('p','entity-detail-note');
      const empty=element('p','entity-detail-empty');
      body.append(note,empty);
      state={body,note,empty};
      if (current==='raw') {
        state.pre=element('pre','raw-data'); body.append(state.pre);
        set(note,'原始接口快照，仅供排查；不混入前端保留的旧值。');
      } else {
        const shell=element('div','table-scroll');
        const table=element('table','data-table entity-detail-table');
        table.append(element('thead',''),element('tbody','')); shell.append(table);
        state.pager=createPager(`${kind==='enemy'?'敌人':'干员'}详情 · ${tab.label}`,draw,15);
        body.append(state.pager.element,shell);
        // The renderer inserts its column controls before this shell.
        state.renderer=createTableRenderer(table,{orderKey:`entity-detail-${kind}-${current}`,orderStore});
      }
      states.set(current,state);
    }
    if (activePanel.firstChild!==state.body) activePanel.append(state.body);
    if (current==='raw') {
      set(state.pre,JSON.stringify(view.raw,null,2));
      state.empty.hidden=true;
      return;
    }
    set(state.note,tab.note || ''); state.note.hidden=!tab.note;
    const page=state.pager.slice(tab.rows);
    state.pager.element.hidden=!tab.rows.length;
    set(state.empty,tab.note || tab.empty || '当前来源没有可展示的记录');
    state.empty.hidden=tab.rows.length>0;
    state.renderer.update(tab.columns || [],page.items,(row,column)=>row[column.key]);
    state.body.querySelector('.table-scroll').hidden=!tab.rows.length;
  }
  function installTabs() {
    buttons=view.tabs.map(tab=>{
      const button=element('button','',tab.label); button.type='button';
      button.dataset.tab=tab.id; button.id=`${prefix}-tab-${tab.id}`;
      button.setAttribute('role','tab'); button.setAttribute('aria-controls',`${prefix}-panel-${tab.id}`);
      const body=element('section','entity-detail-tab-panel');
      body.id=`${prefix}-panel-${tab.id}`;body.tabIndex=0;body.hidden=true;
      body.setAttribute('role','tabpanel');body.setAttribute('aria-labelledby',button.id);
      panels.set(tab.id,body);panel.append(body);
      button.onclick=()=>{current=tab.id;draw();};
      button.onkeydown=event=>{
        const index=buttons.indexOf(button); let target;
        if(event.key==='ArrowRight') target=(index+1)%buttons.length;
        else if(event.key==='ArrowLeft') target=(index+buttons.length-1)%buttons.length;
        else if(event.key==='Home') target=0;
        else if(event.key==='End') target=buttons.length-1;
        else return;
        event.preventDefault(); buttons[target].click(); buttons[target].focus();
      };
      return button;
    });
    tabHost.replaceChildren(...buttons);
  }
  return {element:root,update(input) {
    view=model.project(input);
    if(!buttons.length) installTabs();
    set(status,view.status);
    for(const [domain,node] of [['basic',basicFrame],['detail',detailFrame]]) {
      const summary=view.frames[domain];set(node,summary.text);
      if(node.title!==summary.title) node.title=summary.title;
      if(node.dataset.freshness!==summary.freshness) node.dataset.freshness=summary.freshness;
    }
    draw(); return view;
  },updateClock(clock={}) {
    set(clockTime,formatClock(clock.gameTime));set(clockFrame,clock.fixedFrame ?? '—');
    clockTime.title=clock.connected?'复用主工作台游戏时钟':'时钟连接不可用，最后已知读数';
  },destroy() {
    tabHost.removeAttribute('role');tabHost.removeAttribute('aria-label');tabHost.replaceChildren();
    root.replaceChildren();states.clear();panels.clear();view=null;
  }};
}
