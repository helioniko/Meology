'use strict';
const csrf=document.querySelector('meta[name=memory-csrf]').content;
let webDraft=null;
let state={},currentView='chat',sessionId='',messageSignature='',wizardStep=0,navigationVersion=0,journalTab='raw',memoryTab='pending',toastTimer,onboarding=null,wizardSelected=[],wizardReturnView='chat',wizardFresh=false,wizardBusy=false;
const view=document.getElementById('view');
function el(tag,props={},...children){const node=document.createElement(tag);for(const [key,value] of Object.entries(props)){if(value===undefined)continue;if(key.startsWith('on'))node[key]=event=>Promise.resolve(value(event)).catch(error=>toast(error.message));else if(key==='text')node.textContent=value;else node[key]=value;}for(const child of children.flat()){if(child!==null&&child!==undefined)node.append(typeof child==='string'?document.createTextNode(child):child);}return node;}
function button(text,fn,cls=''){return el('button',{text,onclick:fn,className:cls,type:'button'});}
function toast(text){const node=document.getElementById('toast');node.textContent=text;node.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>node.hidden=true,5500);}
async function api(path,data){const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:data===undefined?{}:{'Content-Type':'application/json','X-Memory-CSRF':csrf},body:data===undefined?undefined:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw new Error(errorText(result.error||t("操作未完成")));if(data!==undefined){clearTimeout(refreshTimer);refreshTimer=setTimeout(pollState,750);}return result;}
function field(name,label,type='text',value=''){const input=el(type==='textarea'?'textarea':'input',{name,value:String(value??''),type:type==='textarea'?undefined:type});return el('label',{className:'form-label'},label,input);}
function choiceField(name,label,choices,value){const select=el('select',{name,id:name});const items=[...choices];if(!items.some(([v])=>String(v)===String(value)))items.push([value,String(value)+t("（现有设置）")]);for(const [v,text] of items)select.append(el('option',{value:String(v),text,selected:String(v)===String(value)}));return el('label',{className:'form-label'},label,select);}
function check(name,label,value){return el('label',{className:'check'},el('input',{type:'checkbox',name,checked:!!value}),label);}
function formValues(form){const result={};for(const input of form.elements){if(input.name)result[input.name]=input.type==='checkbox'?input.checked:input.value;}return result;}
function empty(title,description){return el('div',{className:'empty'},el('div',{className:'empty-mark',text:t("拾")}),el('h2',{text:title}),el('p',{text:description}));}
function closeModal(){document.getElementById('modal').close();}
function modal(title,content){const body=document.getElementById('modal-body');body.replaceChildren(el('div',{className:'toolbar'},el('h2',{text:title}),button(t("关闭"),closeModal,'subtle')),content);document.getElementById('modal').showModal();}
function native(method,...args){if(window.pywebview?.api?.[method])return window.pywebview.api[method](...args);return Promise.resolve(null);}
function stamp(value){return value?value.slice(0,16).replace('T',' '):'';}
async function refreshState(){state=await api('/api/state');setLanguage(state.settings.language);applyAppearance(state.appearance);document.getElementById('today-label').textContent=state.today+t(" · 数据保存在本机");document.getElementById('pending-count').textContent=state.pending||'';const jobs=state.jobs||[];const webMode=state.settings.ai_mode==='web';let text=webMode?t("网页 AI 模式 · 在设置中准备并回填整理结果"):!state.ai_ready?t("记录随时可保存 · 配置 AI 后自动整理"):tf("AI 已连接配置 · 今日调用 {0}/{1}",state.usage.calls,state.settings.daily_call_limit);if(jobs.some(j=>j.status==='running'))text+=t(" · 正在处理");else if(jobs.length)text+=tf(" · {0} 项待处理",jobs.length);const strip=document.getElementById('status-strip');strip.replaceChildren(el('span',{text}));if(!state.ai_ready)strip.append(button(webMode?t("网页整理"):t("配置 AI"),()=>showView('settings')));if(jobs.some(j=>j.status==='failed'||j.status==='retry'||j.status==='budget'))strip.append(button(t("查看任务"),()=>showView('settings')));}
async function showView(name){const version=++navigationVersion;currentView=name;document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===name));view.replaceChildren(el('p',{text:t("正在读取…"),className:'loading'}));await refreshState();document.getElementById('view-title').textContent=({chat:t("随手记"),profile:t("我的档案"),journal:t("记录与回顾"),memory:t("记忆"),connect:t("连接其他 AI"),settings:t("设置"),agenda:t("日程")})[name];native('set_language',state.settings.language,name).catch(()=>{});if(version!==navigationVersion)return;if(name==='chat')await renderChat();if(name==='profile')renderProfile();if(name==='journal')await renderJournal();if(name==='memory')await renderMemory();if(name==='settings')await renderSettings();if(name==='connect')await renderConnections();if(name==='agenda')await renderAgenda();}
async function renderChat(){if(currentView!=='chat')return;if(!sessionId||!state.sessions.some(s=>s.id===sessionId))sessionId=state.sessions[0]?.id||(await api('/api/session',{})).id;const select=el('select',{onchange:async e=>{sessionId=e.target.value;messageSignature='';await loadMessages();}});const sessions=await api('/api/state');if(currentView!=='chat')return;for(const s of sessions.sessions)select.append(el('option',{value:s.id,text:s.title==='新的记录'?t(s.title):s.title,selected:s.id===sessionId}));const top=el('div',{className:'chat-top'},select,button(t("新的一段"),async()=>{sessionId=(await api('/api/session',{})).id;await refreshState();await renderChat();}));const messages=el('div',{id:'messages',className:'messages'});const textarea=el('input',{id:'compose',type:'text',placeholder:t("今天发生了什么？或者，想到什么就写下来。"),maxLength:20000,ariaLabel:t("记录事件和想法")});const share=check('share',t("由 AI 提取关键信息"),true);const sendButton=button(t("发送"),async()=>{const text=textarea.value.trim();if(!text)return;sendButton.disabled=true;const requestId=crypto.randomUUID();try{await api('/api/send',{session_id:sessionId,content:text,share_with_ai:share.querySelector('input').checked,request_id:requestId});textarea.value='';await refreshState();messageSignature='';await loadMessages();await renderChatAgenda();if(!state.ai_ready&&share.querySelector('input').checked)toast(state.settings.ai_mode==='web'?t("输入已暂存，请在设置中使用网页整理；整理成功后清除原文。"):t("输入已暂存，配置 AI 后提取关键信息，成功后清除原文。"));}finally{sendButton.disabled=false;}},'primary');textarea.onkeydown=e=>{if(e.key==='Enter'&&!e.isComposing){e.preventDefault();sendButton.click();}};const composer=el('div',{className:'composer single-line-composer'},textarea,share,sendButton);const agenda=el('section',{id:'chat-agenda',className:'chat-agenda'});view.replaceChildren(el('div',{className:'chat-layout'},top,agenda,messages,composer));messageSignature='';await loadMessages();await renderChatAgenda();}
async function loadMessages(){if(currentView!=='chat')return;const rows=await api('/api/messages?session='+encodeURIComponent(sessionId));if(currentView!=='chat')return;const sig=JSON.stringify(rows);if(sig===messageSignature)return;messageSignature=sig;const container=document.getElementById('messages');if(!container)return;const stick=container.scrollHeight-container.scrollTop-container.clientHeight<90;container.replaceChildren();if(!rows.length){const welcome=empty(state.profile.name?tf("{0}，今天过得怎样？",state.profile.name.content):t("从一件小事开始。"),t("重要的事情、突然的想法、还没想清楚的感受，都可以直接告诉我。"));welcome.append(el('div',{className:'suggestions'},button(t("今天发生了一件事"),()=>{document.getElementById('compose').value=t("今天发生了一件事：");document.getElementById('compose').focus();}),button(t("记下一个新想法"),()=>{document.getElementById('compose').value=t("我刚想到：");document.getElementById('compose').focus();})));container.append(welcome);}for(const row of rows){if(row.role!=='user')continue;container.append(el('div',{className:'message '+row.role},el('div',{className:'message-header',text:(row.role==='user'?t("我"):t("拾记"))+' · '+stamp(row.created_at)+(row.role==='user'&&!row.share_with_ai?t(" · 仅本地"):'')+(row.retention_state==='compact'?t(" · 当前档案信息"):t(" · 临时输入"))+(row.model?' · '+row.model:'') }),el('div',{className:'bubble',text:row.content})));}if(stick)container.scrollTop=container.scrollHeight;}
function profileForm(fields){const form=el('form',{});for(const item of fields){const [key,label,group,type]=item;const current=state.profile[key];form.append(field(key,key.startsWith('custom.')?label:t(label),type,current?.content||''),el('div',{className:'share-field'},check(key+'__share',t("允许 AI 使用这一项"),current?current.share_with_ai:true)));}form.onsubmit=e=>e.preventDefault();return form;}
function profilePayload(form){const values=formValues(form),result={};for(const [key] of state.fields)if(key in values)result[key]={value:values[key],share_with_ai:values[key+'__share']};return result;}
function renderProfile(){
 const filled=state.fields.filter(([key])=>state.profile[key]);
 const added=filled.filter(([key])=>key.startsWith('custom.')).length;
 const intro=el('div',{className:'toolbar'},el('p',{text:t("生活、关系、健康、学习、工作、财务、经历与想法等各方面，都能发现新主题并增加细节；同一属性的变化保留历史。核心信息和 AI 推测由你审核。"),className:'muted'}),button(t("选择方向，补充资料"),()=>openWizard(true),'primary'));
 intro.append(button(t("聊一条新信息"),async()=>{await showView('chat');document.getElementById('compose')?.focus();},'subtle'));
 if(filled.length)intro.append(button(t("编辑已填资料"),()=>editProfile()));
 intro.append(el('a',{href:'/context',text:t("导出给 AI"),download:'ai-context.md'}));view.replaceChildren(intro,el('p',{className:'muted',id:'profile-growth',text:tf("已记录 {0} 项资料 · 扩展条目 {1} 项",filled.length,added)}));
 const learned='从记录逐步理解';
 for(const group of [...new Set(filled.map(f=>f[2]))].filter(g=>g!==learned)){
  const card=el('section',{className:'card'},el('h3',{text:t(group)}));
  for(const [key,label] of filled.filter(f=>f[2]===group))appendProfileRow(card,key,label);
  view.append(card);
 }
 if(!filled.length)view.append(empty(t("从你愿意填写的方向开始。"),t("可以先填写基础信息，也可以直接聊天；新方向、新对象和新属性会随着记录逐步加入。")));
 const understanding=el('section',{className:'card'},el('h3',{text:t("从记录逐步理解你")}),el('p',{className:'muted',text:t("价值观、重要边界、思考与行动模式等，不在初次建档时提问。后续 AI 有依据的总结会作为候选，经过你审核后才写入核心档案。")}));
 for(const [key,label] of filled.filter(f=>f[2]===learned))appendProfileRow(understanding,key,label);
 understanding.append(button(t("查看核心审核"),()=>showView('memory'),'subtle'));view.append(understanding);
}
function appendProfileRow(card,key,label){const r=state.profile[key];card.append(el('div',{className:'field-row'},el('small',{text:(key.startsWith('custom.')?label:t(label))+(r.share_with_ai?t(" · AI 可用"):t(" · 仅本地"))}),el('div',{className:'field-value',text:r.content})),button(t("查看修改历史"),()=>showHistory(r.id),'subtle'));if(key==='birth_date'&&state.age!==null)card.append(el('p',{className:'muted',text:t("当前年龄：")+state.age+t(" 岁（由出生日期计算）")}));}
function editProfile(){const form=profileForm(state.fields.filter(([key])=>state.profile[key]));form.prepend(el('p',{className:'muted',text:t("这里修改已保存的条目，主动清空会归档。问卷用于补充基础资料；日常聊天发现的新属性也会自动新增并显示在档案中。")}));form.append(button(t("保存档案"),async()=>{if(!form.reportValidity())return;await api('/api/profile',{fields:profilePayload(form)});closeModal();await showView('profile');toast(t("档案已更新，修改历史已保留。"));},'primary'));modal(t("编辑已填资料"),form);}

async function showHistory(id){const rows=await api('/api/history?id='+id);const list=el('div',{});if(!rows.length)list.append(el('p',{text:t("还没有修改历史。"),className:'muted'}));for(const row of rows){const snap=JSON.parse(row.snapshot);list.append(el('section',{className:'card'},el('small',{className:'muted',text:stamp(row.changed_at)+t(" · 修改前")}),el('h3',{text:snap.title}),el('div',{className:'raw-text',text:snap.content}),el('p',{className:'muted',text:t("来源：")+snap.source}),button(t("恢复这一版"),async()=>{await api('/api/revision',{id:row.id});closeModal();await showView(currentView);toast(t("已恢复，恢复前的版本也已保留。"));})));}modal(t("档案与记录历史"),list);}
async function renderJournal(){if(currentView!=='journal')return;const controls=el('div',{className:'toolbar'},el('div',{className:'tabs'},...['raw','daily','weekly'].map(key=>button(({raw:t("关键信息"),daily:t("日报"),weekly:t("周报")})[key],async()=>{journalTab=key;await renderJournal();},journalTab===key?'active':''))),button(t("整理今天"),async()=>{await api('/api/organize',{});await refreshState();toast(t("已加入整理队列，已有结果不会重复处理。"));}));view.replaceChildren(controls);if(journalTab==='raw'){const input=el('input',{placeholder:t("搜索记录中的事情、人物或想法")});const results=el('div',{});let offset=0;const load=async()=>{const rows=await api('/api/records?kind=journal&limit=100&offset='+offset+'&q='+encodeURIComponent(input.value));if(currentView!=='journal')return;results.querySelector('.load-more')?.remove();if(!rows.length&&!offset)results.append(empty(t("这里会留下重要经历和想法。"),t("普通事实归入档案；值得回顾的经历保留简短时间线。")));for(const r of rows)results.append(recordCard(r));offset+=rows.length;if(rows.length===100)results.append(button(t("加载更多"),load,'load-more'));};const search=async()=>{offset=0;results.replaceChildren();await load();};view.append(el('div',{className:'toolbar'},input,button(t("搜索"),search)),results);input.onkeydown=e=>{if(e.key==='Enter')search().catch(error=>toast(error.message));};await search();}else{const rows=(await api('/api/summaries')).filter(r=>r.type===journalTab);if(currentView!=='journal')return;if(!rows.length)view.append(empty(t("回顾正在积累。"),t("配置 AI 后，程序会自动整理已结束的日期；今天也可以手动整理。")));for(const r of rows){const card=el('section',{className:'card'},el('span',{className:'badge',text:r.status==='confirmed'?t("已确认"):t("AI 整理 · 待核对")}),el('h3',{text:r.period+(r.type==='weekly'?t(" 开始的一周"):'')}),el('div',{className:'raw-text',text:r.summary}));for(const [key,label] of [['events',t("重要事件")],['ideas',t("想法与变化")]]){let items=JSON.parse(r[key]);if(!Array.isArray(items))items=[];if(items.length)card.append(el('h3',{text:label}),el('ul',{},...items.map(text=>el('li',{text:String(text)}))));}card.append(button(t("查看来源信息"),()=>showSources(JSON.parse(r.source_ids),'records'),'subtle'));if(r.status!=='confirmed')card.append(button(t("确认这份回顾"),async()=>{await api('/api/summary/confirm',{id:r.id});await renderJournal();}));card.append(button(t("删除回顾"),()=>deleteSummary(r),'subtle'));view.append(card);}}}
function recordCard(r){if((r.field_key||'').startsWith('task.'))return el('section',{className:'card'},el('h3',{text:r.title}),el('div',{className:'raw-text',text:r.content}),button(t("在日程页查看"),()=>showView('agenda')));return el('article',{className:'card'},el('span',{className:'badge',text:r.content_state==='pending'?t("待整理 · 临时输入"):({profile:t("核心档案"),state:t("当前状态"),journal:t("日常记录"),project:t("项目与目标"),decision:t("决定与经验"),resource:t("资料来源"),memory:t("长期记忆")})[r.kind]}),el('h3',{text:r.title}),el('div',{className:'raw-text',text:r.content}),el('div',{className:'meta',text:(r.event_date||t("未填写日期"))+' · '+r.source+(r.share_with_ai&&r.sensitivity==='normal'?t(" · AI 可用"):t(" · 仅本地"))}),el('div',{className:'button-row'},button(t("编辑"),()=>editRecord(r),'subtle'),button(t("历史"),()=>showHistory(r.id),'subtle'),r.kind==='journal'?button(t("删除"),()=>deleteJournal(r),'subtle'):null,button(r.archived?t("恢复记录"):t("归档"),async()=>{await api('/api/archive',{id:r.id,archived:!r.archived});await showView(currentView);},'subtle')));}
async function deleteJournal(r){
 if(!confirm(t("删除“")+r.title+t("”及其修改历史？未完成的整理也会取消，此操作无法撤销，已有备份仍保留。")))return;
 await api('/api/record/delete',{id:r.id});messageSignature='';await showView(currentView);toast(t("记录已删除。"));
}
async function deleteSummary(r){
 if(!confirm(t("删除这份回顾？来源记录会保留，原有内容不会自动重新生成相同回顾。")))return;
 await api('/api/summary/delete',{id:r.id});await showView('journal');toast(t("回顾已删除。该时段有新内容后可生成新的回顾。"));
}
async function showSources(ids,type){const rows=await api(type==='records'?'/api/records?ids='+ids.join(','):'/api/messages?ids='+ids.join(','));const selected=rows.filter(r=>ids.includes(r.id));modal(t("来源信息"),el('div',{},...selected.map(r=>el('section',{className:'card'},el('small',{className:'muted',text:'#'+r.id+' · '+stamp(r.created_at)}),el('div',{className:'raw-text',text:r.content})))));}
function editRecord(r={}){const form=el('form',{});form.onsubmit=e=>e.preventDefault();const kind=el('select',{name:'kind'});for(const [key,title] of Object.entries({state:t("当前状态"),memory:t("长期记忆"),project:t("项目与目标"),decision:t("决定与经验"),resource:t("资料来源"),journal:t("日常记录"),profile:t("核心档案")}))kind.append(el('option',{value:key,text:title,selected:key===(r.kind||'state')}));form.append(el('label',{className:'form-label'},t("类型"),kind),field('title',t("标题"),'text',r.title||''),field('content',t("内容"),'textarea',r.content||''),field('source',t("来源"),'text',r.source||t("本人填写")),field('tags',t("标签（用逗号分隔，留空自动生成）"),'text',r.tags||''),field('event_date',t("日期"),'date',r.event_date||state.today),check('share_with_ai',t("允许 AI 使用"),r.share_with_ai??true));form.append(button(t("保存"),async()=>{const data=formValues(form);await api('/api/record/save',{id:r.id,record:{...r,...data,category:r.category||'其他',status:'confirmed',sensitivity:data.share_with_ai?'normal':'sensitive'}});closeModal();await showView(currentView);},'primary'));modal(r.id?t("编辑记录"):t("补充一条记忆"),form);}
async function renderMemory(){
 if(currentView!=='memory')return;
 view.replaceChildren(el('div',{className:'toolbar'},el('div',{className:'tabs'},...['pending','saved','archive'].map(key=>button(({pending:t("核心审核"),saved:t("已保存"),archive:t("已归档")})[key],async()=>{memoryTab=key;await renderMemory();},memoryTab===key?'active':''))),button(t("手动补充"),()=>editRecord())));
 if(memoryTab==='pending'){
  const rows=(await api('/api/proposals')).filter(p=>p.status==='pending'&&p.review_level==='core');if(currentView!=='memory')return;
  if(!rows.length){view.append(empty(t("没有需要审核的核心信息。"),t("日常事件与普通想法会自动整理，核心档案修改才需要你审核。")));return;}
  const selected=new Set(),expected={};
  const submit=async(ids,action)=>{await api('/api/review',{ids,action,expected});await refreshState();await renderMemory();toast(action==='confirmed'?t("核心信息已更新，旧值保留在历史中。"):t("已拒绝，当前档案保留。"));};
  view.append(el('p',{className:'muted',text:t("以下是全部待审核的核心信息。批准前不会覆盖档案，也不会作为已确认资料提供给其他 AI。")}),el('div',{className:'button-row'},button(t("通过所选修改"),()=>{if(!selected.size)throw new Error(t("请先勾选需要通过的修改"));return submit([...selected],'confirmed');},'primary'),button(t("拒绝所选修改"),()=>{if(!selected.size)throw new Error(t("请先勾选需要拒绝的修改"));return submit([...selected],'rejected');},'subtle')));
  for(const p of rows){
   const old=p.field_key?state.profile[p.field_key]?.content||'':'';expected[String(p.id)]=old;
   const checkbox=el('input',{type:'checkbox',onchange:e=>{e.target.checked?selected.add(p.id):selected.delete(p.id);}});
   const card=el('article',{className:'card review-card'},el('label',{className:'check'},checkbox,t("选择：")+p.title),el('span',{className:'badge warn',text:p.field_key?t("核心档案修改"):t("重要核心信息")}),el('h3',{text:p.title}));
   if(p.field_key)card.append(el('p',{className:'muted',text:t("当前值：")+(old||t("尚未填写"))}));
   card.append(el('div',{className:'raw-text',text:t("建议值：")+p.content}),el('p',{className:'muted',text:t("原因：")+(p.reason||t("涉及核心个人信息"))}),el('small',{className:'muted',text:t("来源：记录 #")+JSON.parse(p.source_ids).join('、')+' · '+stamp(p.created_at)}),el('div',{className:'button-row'},button(t("通过修改"),()=>submit([p.id],'confirmed'),'primary'),button(t("拒绝修改"),()=>submit([p.id],'rejected'),'subtle'),button(t("查看来源信息"),()=>showSources(JSON.parse(p.source_ids),'messages'),'subtle')));view.append(card);
  }
 }else{
  let offset=0;const tab=memoryTab;
  const load=async()=>{
   const rows=await api('/api/records?limit=100&offset='+offset+(tab==='archive'?'&archived=1':'&view=memory'));
   if(currentView!=='memory'||memoryTab!==tab)return;
   view.querySelector('.load-more')?.remove();if(!rows.length&&!offset)view.append(empty(t("让记忆慢慢积累。"),t("日常关键信息自动保存，重要的核心变化经审核后更新。")));
   for(const r of rows)view.append(recordCard(r));offset+=rows.length;
   if(rows.length===100)view.append(button(t("加载更多"),load,'load-more'));
  };await load();
 }
}
let agendaFilter='pending',agendaOffset=0;
function agendaDate(item){return item.due_at?item.due_at.replace('T',' '):t("未指定日期");}
async function changeAgenda(item,status){await api('/api/agenda/status',{id:item.id,status});if(currentView==='agenda')await renderAgenda();else await renderChatAgenda();toast(status==='done'?t("已完成，可在日程页恢复。"):status==='cancelled'?t("已取消这项日程。"):t("已恢复到待办。"));}
function agendaCard(item){
 const card=el('section',{className:'card agenda-item','data-id':item.id},el('div',{className:'agenda-item-heading'},el('h3',{text:item.title}),el('span',{className:'badge',text:({pending:t("待办"),done:t("已完成"),cancelled:t("已取消")})[item.status]})),el('p',{className:'agenda-date',text:agendaDate(item)}),el('div',{className:'raw-text',text:item.description}));
 card.append(el('div',{className:'button-row'},item.status==='pending'?button(t("完成"),()=>changeAgenda(item,'done'),'primary'):button(t("恢复待办"),()=>changeAgenda(item,'pending')),button(t("编辑日程"),()=>editAgenda(item)),item.status==='pending'?button(t("取消"),()=>changeAgenda(item,'cancelled'),'subtle'):null,button(t("查看历史"),()=>showHistory(item.id),'subtle')));return card;
}
async function editAgenda(item){
 const form=el('form',{});form.onsubmit=e=>e.preventDefault();
 const precision=el('select',{name:'precision',ariaLabel:t("时间精度")},el('option',{value:'none',text:t("未指定日期")}),el('option',{value:'date',text:t("只有日期")}),el('option',{value:'time',text:t("日期和时间")}));precision.value=item.precision;
 const due=el('input',{name:'due_at',ariaLabel:t("日程时间"),type:item.precision==='time'?'datetime-local':'date',value:item.due_at});due.hidden=item.precision==='none';due.required=item.precision!=='none';
 precision.onchange=()=>{due.hidden=precision.value==='none';due.required=precision.value!=='none';const previous=due.value;due.type=precision.value==='time'?'datetime-local':'date';due.value=precision.value==='time'?(previous.length>10?previous:''):previous.slice(0,10);};
 form.append(field('title',t("日程事项"),'text',item.title),field('description',t("事项内容"),'textarea',item.description),el('label',{className:'form-label'},t("时间精度"),precision),el('label',{className:'form-label'},t("日程时间"),due),button(t("保存日程"),async()=>{if(!form.reportValidity())return;const fields=formValues(form);if(fields.precision==='none')fields.due_at='';await api('/api/agenda/edit',{id:item.id,fields});closeModal();await renderAgenda();toast(t("日程已保存。"));},'primary'));modal(t("编辑日程"),form);
}
async function refreshAgendaRows(append=false){
 if(currentView!=='agenda')return;const selected=agendaFilter,offset=append?agendaOffset:0;const rows=await api('/api/agenda?status='+selected+'&limit=100&offset='+offset);if(currentView!=='agenda'||selected!==agendaFilter)return;
 const list=document.getElementById('agenda-list');if(!list)return;if(!append)list.replaceChildren();list.querySelector('.load-more')?.remove();
 if(!rows.length&&!offset)list.append(empty(t("暂无日程"),t("记录明确的安排或待办，AI 整理后会出现在这里。")));
 for(const item of rows)list.append(agendaCard(item));agendaOffset=offset+rows.length;if(rows.length===100)list.append(button(t("加载更多"),()=>refreshAgendaRows(true),'load-more'));
}
async function renderAgenda(){
 if(currentView!=='agenda')return;const tabs=el('div',{className:'tabs'});for(const [id,title] of [['pending',t("待办")],['done',t("已完成")],['cancelled',t("已取消")],['all',t("全部")]])tabs.append(button(title,async()=>{agendaFilter=id;await renderAgenda();},agendaFilter===id?'active':''));
 view.replaceChildren(el('p',{className:'muted',text:t("AI 定时整理后，明确安排才加入日程；网页模式回填后加入。相对日期按记录时的中国时区计算，未指定具体时间不猜；核心事项仍需审核。")}),tabs,el('div',{id:'agenda-list'}));await refreshAgendaRows();
}
async function renderChatAgenda(){
 if(currentView!=='chat')return;const box=document.getElementById('chat-agenda');if(!box)return;const rows=await api('/api/agenda?limit=3');if(currentView!=='chat'||!box.isConnected)return;
 box.replaceChildren(el('div',{className:'agenda-preview-heading'},el('strong',{text:t("日程")}),button(t("全部"),()=>showView('agenda'),'subtle')));
 if(!rows.length)box.append(el('small',{className:'muted',text:t("暂无待办")}));for(const item of rows)box.append(el('div',{className:'agenda-preview-row'},button('○',()=>changeAgenda(item,'done'),'subtle'),el('span',{text:agendaDate(item)+' · '+item.title,title:item.description})));
}
async function renderSettings(){if(currentView!=='settings')return;const providers=await api('/api/providers');if(currentView!=='settings')return;view.replaceChildren(el('p',{className:'provider-note',text:state.settings.ai_mode==='web'?t("个人数据始终保存在本机。网页模式无需 API 密钥，在下方准备整理内容，再去官网发送并回填回复。"):t("个人数据与模型设置分开保存。切换 AI 后仍使用同一本地数据库。API 按所选周期提取允许分享的相关信息；发送记录时不会调用 AI 回复。")}));appendLanguageSettings();appendTutorialSettings();await appendAIConnectionSettings();await appendAppearanceSettings();if(currentView!=='settings')return;const providerSection=el('section',{className:'card'},el('h3',{text:t("选择使用的 AI")}));const selector=el('select',{id:'provider-select'});selector.append(el('option',{value:'',text:t("添加一套新的 AI 配置")}));for(const p of providers)selector.append(el('option',{value:p.id,text:p.name+' · '+p.model,selected:p.id===state.settings.active_provider}));const editor=el('div',{});function fill(id){const p=providers.find(p=>p.id===id)||{};const form=el('form',{id:'provider-editor'});form.onsubmit=e=>e.preventDefault();form.append(field('name',t("配置名称"),'text',p.name||''),field('base_url',t("API 服务地址（根地址，通常以 /v1 结尾）"),'url',p.base_url||''),field('api_key',t("API 密钥"),'password',''),el('p',{className:'muted',text:p.has_key?t("密钥已在本机加密保存。留空会保留原密钥。"):t("填写后加密保存在 Windows 当前用户账户下，不进入数据导出。")}),field('model',t("默认模型 ID"),'text',p.model||''),field('organizer_model',t("整理模型 ID（留空使用默认模型）"),'text',p.organizer_model||''));const save=button(t("保存并使用"),async()=>{const values=formValues(form);await api('/api/provider/save',{...values,id:p.id,activate:true});toast(t("AI 配置已保存，个人数据保持在原数据库中。"));await showView('settings');},'primary');form.append(el('div',{className:'button-row'},save,button(t("测试连接"),async()=>{if(!p.id)throw new Error(t("请先保存配置"));const result=await api('/api/provider/test',{id:p.id});toast(t("连接成功：")+result.reply);await refreshState();}),button(t("新建配置"),()=>{selector.value='';fill('');},'subtle')));editor.replaceChildren(form);}selector.onchange=e=>fill(e.target.value);fill(selector.value);providerSection.append(selector,editor);providerSection.hidden=state.settings.ai_mode==='web';view.append(providerSection);appendMaintenanceSettings();await appendStorageSettings();const jobs=el('section',{className:'card jobs'},el('h3',{text:t("后台任务")}));if(!state.jobs.length)jobs.append(el('p',{className:'muted',text:t("目前没有待处理任务。")}));for(const j of state.jobs){const label=({chat:t("旧任务（已停用）"),organize:t("记忆整理"),summary:t("生成回顾")})[j.kind]||j.kind;const status=({queued:t("等待处理"),running:t("正在进行"),retry:t("等待重试"),failed:t("需要重试"),budget:t("等待明日预算")})[j.status]||j.status;jobs.append(el('div',{className:'field-row'},el('span',{text:label+' · '+status}),el('small',{text:errorText(j.last_error)||(state.settings.ai_mode==='web'?t("网页整理模式；后台 API 任务暂停"):!state.ai_ready?t("配置 AI 后继续"):t("待整理输入会临时保留"))}),j.status!=='running'?button(t("重试"),async()=>{await api('/api/retry',{id:j.id});await showView('settings');},'subtle'):null));}view.append(jobs);const backupCard=el('section',{className:'card'},el('h3',{text:t("备份与导出")}),el('p',{className:'muted',text:t("每天自动备份一次，保留最近 14 份自动备份；手动备份继续保留。恢复前会再保存一份当前数据库。API 密钥独立加密保存，不随 JSON 导出。")}),el('div',{className:'button-row'},button(t("立即备份"),async()=>{const r=await api('/api/backup',{});toast(t("备份已保存：")+r.path);}),button(t("恢复备份"),showBackups),el('a',{href:'/context',download:'ai-context.md',text:t("导出 AI 背景")}),el('a',{href:'/export',download:'personal-export.json',text:t("导出全部数据")})));view.append(backupCard);}
async function showBackups(){const rows=await api('/api/backups');const list=el('div',{},el('p',{className:'muted',text:t("恢复将用选中的备份替换当前数据库。恢复前会自动保存当前版本。")}));for(const r of rows)list.append(el('div',{className:'field-row'},el('small',{text:r.name+' · '+Math.round(r.size/1024)+' KB'}),button(t("恢复这份备份"),async()=>{if(!confirm(t("确认恢复 ")+r.name+t("？当前数据会先备份。")))return;await api('/api/restore',{name:r.name});closeModal();sessionId='';await refreshState();await showView('chat');toast(t("数据库已恢复。"));}),button(t("删除备份"),async()=>{if(!confirm(t("永久删除备份 ")+r.name+t("？当前数据库不受影响。")))return;await api('/api/backup/delete',{name:r.name});closeModal();await showBackups();},'subtle')));modal(t("备份管理与恢复"),list);}
function wizardGroups(){return onboarding.groups.filter(g=>wizardSelected.includes(g.id));}
async function openWizard(reselect=false){
 onboarding=await api('/api/onboarding');wizardSelected=[...onboarding.progress.selected];
 const groups=wizardGroups(),index=groups.findIndex(g=>g.id===onboarding.progress.current_group);
 wizardStep=reselect?0:(index<0?0:index+1);wizardFresh=!state.settings.onboarding_complete;wizardReturnView=wizardFresh?'chat':currentView;
 renderWizard();const dialog=document.getElementById('onboarding');if(!dialog.open)dialog.showModal();document.querySelector('#wizard-body input, #wizard-body select, #wizard-body textarea')?.focus({preventScroll:true});
}
function questionnaireForm(group){
 const form=el('form',{});form.onsubmit=e=>e.preventDefault();
 form.append(el('p',{className:'muted',text:t("每项都可留空。")+(group.share_default?t("逐项决定是否允许 AI 使用。"):t("这个方向默认仅保存在本地，可逐项允许 AI 使用。"))}));
 for(const q of group.questions){
  const current=state.profile[q.key],value=current?.content||'';let input;
  if(q.type==='select'){
   input=el('select',{name:q.key},el('option',{value:'',text:current&&!q.choices.includes(value)?t("留空，保留已存答案"):t("暂不填写")}),q.choices.map(v=>el('option',{value:v,text:t(v)})));
   input.value=q.choices.includes(value)?value:'';
  }else{
   input=el(q.type==='textarea'?'textarea':'input',{name:q.key,value,type:q.type==='textarea'?undefined:q.type,placeholder:t(q.example),maxLength:3000});
   if(q.minimum!==null)input.min=String(q.minimum);
   if(q.maximum!==null)input.max=q.maximum==='current_year'?String(new Date().getFullYear()):String(q.maximum);
   if(q.type==='number')input.step=q.key==='work_start_year'?'1':'any';
   if(q.key==='birth_date')input.max=state.today;
  }
  const inputId='answer-'+q.key;input.id=inputId;
  const block=el('div',{className:'question-block'},el('label',{className:'form-label',htmlFor:inputId,text:t(q.prompt)}),input);
  if(q.example)block.append(el('small',{className:'question-help',text:t(q.example)}));
  if(q.type==='select'&&current&&!q.choices.includes(value))block.append(el('small',{className:'question-help',text:t("已保存：")+value}));
  block.append(check(q.key+'__share',t("允许 AI 使用这一项"),current?current.share_with_ai:group.share_default));form.append(block);
 }
 return form;
}
function updateWizardProgress(){document.getElementById('wizard-progress').replaceChildren(...Array.from({length:wizardGroups().length+1},(_,i)=>el('span',{className:i<=wizardStep?'done':''})));}
function updateWizardSelection(){wizardSelected=onboarding.groups.filter(g=>document.querySelector(`#wizard-body input[name="direction-${g.id}"]`)?.checked).map(g=>g.id);updateWizardProgress();updateWizardActions();document.getElementById('direction-count').textContent=tf("已选 {0} 个方向，可以先选一个。",wizardSelected.length);}
function updateWizardActions(){
 const groups=wizardGroups(),next=document.getElementById('wizard-next'),back=document.getElementById('wizard-back');
 next.textContent=wizardStep===0?tf("开始填写（{0}）",groups.length):wizardStep===groups.length?t("完成建档"):t("保存并继续");
 next.disabled=wizardBusy||(wizardStep===0&&!groups.length);back.disabled=wizardBusy||wizardStep===0;back.textContent=wizardStep===1?t("重选方向"):t("上一步");
 document.getElementById('wizard-skip').textContent=wizardStep===0?t("暂时不填"):t("保存并结束");document.getElementById('wizard-skip').disabled=wizardBusy;
}
function renderWizard(){
 const groups=wizardGroups(),body=document.getElementById('wizard-body');
 updateWizardProgress();
 body.replaceChildren();
 if(wizardStep===0){
  body.append(el('h3',{text:t("你想先填写哪些方面？")}),el('p',{id:'direction-count',className:'muted',text:tf("已选 {0} 个方向，可以先选一个。",groups.length)}));
  const choices=el('div',{className:'direction-grid'});
  for(const group of onboarding.groups){
   const input=el('input',{type:'checkbox',name:'direction-'+group.id,checked:wizardSelected.includes(group.id),onchange:updateWizardSelection});
   const label=el('label',{className:'direction-choice'},input,el('span',{},el('strong',{text:t(group.label)}),el('small',{text:t(group.description)}),el('small',{className:'direction-count',text:tf("{0} 道可选问题{1}",group.questions.length,group.share_default?'':t(" · 默认仅本地"))})));
   choices.append(label);
  }
  body.append(choices,el('div',{className:'wizard-later'},el('strong',{text:t("这些留给以后的记录")}),el('p',{text:t("价值观、决策原则、思考模式和情绪规律，不需要现在自己总结。AI 有依据时提出总结，关键内容由你审核。")})));
 }else{
  const group=groups[wizardStep-1];body.append(el('span',{className:'eyebrow',text:tf("填写 {0} / {1}",wizardStep,groups.length)}),el('h3',{text:t(group.label)}),el('p',{className:'muted',text:t("只填写你已经知道、愿意提供的答案；留空会保留已填资料。")}),questionnaireForm(group));
 }
 body.scrollTop=0;updateWizardActions();
}
async function wizardAction(action){
 if(wizardBusy)return;const form=document.querySelector('#wizard-body form');if(form&&!form.reportValidity())return;
 if(wizardStep===0)updateWizardSelection();const groups=wizardGroups();
 if(action==='next'&&wizardStep===0&&!groups.length)return;
 const finish=action==='finish'||(action==='next'&&wizardStep===groups.length&&wizardStep>0);
 const nextStep=finish?0:action==='back'?wizardStep-1:wizardStep+1;
 wizardBusy=true;updateWizardActions();
 try{
  onboarding=await api('/api/onboarding',{questionnaire_version:onboarding.questionnaire_version,selected:wizardSelected,current_group:nextStep?groups[nextStep-1].id:'',finish,fields:form?profilePayload(form):{}});
  await refreshState();wizardStep=nextStep;
  if(finish){document.getElementById('onboarding').close();await showView(wizardReturnView);if(wizardFresh)await native('compact');toast(t("已保存填写的信息。之后可在“我的档案”继续选择方向。"));}
  else renderWizard();
 }catch(e){toast(e.message);}finally{wizardBusy=false;updateWizardActions();}
}
document.getElementById('wizard-back').onclick=()=>wizardAction('back');
document.getElementById('wizard-skip').onclick=()=>wizardAction('finish');
document.getElementById('wizard-next').onclick=()=>wizardAction('next');
document.getElementById('onboarding').addEventListener('cancel',e=>e.preventDefault());
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>showView(b.dataset.view).catch(e=>toast(e.message)));document.getElementById('resize-window').onclick=()=>native('toggle_size').catch(e=>toast(e.message));document.getElementById('pin-window').onclick=async()=>{const pinned=await native('toggle_pin');toast(pinned?t("窗口已置顶"):t("已取消置顶"));};window.setDesktopMode=enabled=>{document.body.classList.toggle('embedded',!!enabled);const button=document.getElementById('embed-window');button.textContent=enabled?t("↗ 恢复窗口"):t("▦ 嵌入桌面");button.title=enabled?t("恢复可移动、可缩放的普通窗口"):t("固定到 Windows 桌面，隐藏标题栏并锁定大小");button.setAttribute('aria-pressed',String(!!enabled));document.getElementById('widget-mode-label').textContent=enabled?t("已固定到桌面"):t("拾记 · 个人记忆");};document.getElementById('embed-window').onclick=async()=>{const button=document.getElementById('embed-window');button.disabled=true;try{const result=await native('toggle_desktop');if(result){if(result.error)throw new Error(result.error);window.setDesktopMode(result.embedded);toast(result.embedded?t("已固定到桌面。顶部按钮或托盘可以恢复窗口。"):t("已恢复普通窗口，可以移动和调整大小。"));}}catch(e){toast(e.message);}finally{button.disabled=false;}};window.addEventListener('pywebviewready',async()=>{if(new URLSearchParams(location.search).has('panel'))return;document.body.classList.add('desktop');const result=await native('desktop_state');if(result)window.setDesktopMode(result.embedded);});
let refreshTimer;
async function pollState(){
 clearTimeout(refreshTimer);
 if(!document.hidden){
  try{const previous=JSON.stringify(state.profile),pending=state.pending;await refreshState();if(currentView==='chat'){await loadMessages();await renderChatAgenda();}if(currentView==='agenda'&&agendaOffset<=100)await refreshAgendaRows();if(currentView==='profile'&&JSON.stringify(state.profile)!==previous)renderProfile();if(currentView==='memory'&&memoryTab==='pending'&&(pending!==state.pending||(state.pending&&!document.querySelector('.review-card'))))await renderMemory();}
  catch(e){document.getElementById('status-strip').textContent=t("本地服务连接中断，请重新打开拾记。");}
 }
 refreshTimer=setTimeout(pollState,document.hidden?60000:(state.settings.ai_mode!=='web'&&state.jobs?.some(j=>['queued','running','retry'].includes(j.status))?2000:30000));
}
const tutorialPages=[
 {mark:'01',title:'从随手记录，慢慢认识你',lead:'拾记会把你提供的信息整理成一份持续成长的个人档案。',items:[
  ['先填你愿意提供的资料','看完教程后，选择想填写的方向，再回答具体问题。每项都可以跳过，之后随时补充。'],
  ['从生活里的小事开始','今天发生的事、一个新想法、刚学会的东西，都可以直接写下来，无需自己分类或贴标签。'],
  ['档案会持续增加','AI 整理时可以发现新的主题和属性，让档案逐渐详细；切换 AI 服务仍使用同一份资料。']
 ]},
 {mark:'02',title:'在小窗里，写一句就能记',lead:'平常使用小窗；查看和管理详细内容时，再打开大窗口。',items:[
  ['写下内容，点击发送','在底部输入事件或想法，点击发送或按 Enter。成功提示出现后，输入已保存在本机。'],
  ['由你决定是否交给 AI','勾选「AI 整理」后，这条输入等待 AI 提取；取消勾选则仅本地保存，不发送给 AI。'],
  ['管理、固定和退出','「管理」打开档案、日程、审核和设置；顶部桌面按钮固定或恢复小窗；退出程序请使用系统托盘菜单。']
 ]},
 {mark:'03',title:'选一种适合你的 AI 整理方式',lead:'发送只负责保存输入，AI 用来提取关键信息，不在小窗里生成聊天回复。',items:[
  ['API 模式：按周期自动整理','在设置中填写服务地址、密钥和模型。默认每小时集中整理一次，可改为 10 分钟、半小时、半天或一天。'],
  ['网页模式：复制、发送、回填','在设置中选择 DeepSeek 或豆包，复制准备好的内容到官网发送，再把完整 JSON 回复粘贴回来并应用。这个流程需要手动完成。'],
  ['暂时不配置也能记录','未配置 AI 时，输入保留在本地待整理；成功提取后清除原始输入，只保存关键信息。失败时保留输入，等待重试。']
 ]},
 {mark:'04',title:'查看成长的档案和日程',lead:'普通信息自动整理，核心信息和 AI 推测先由你审核。',items:[
  ['我的档案：看资料怎样变详细','这里汇总已保存的个人资料。可补充初建问卷、编辑已填信息，并查看重要变化的历史。'],
  ['记忆审核：集中确认关键变化','身份、重要关系、重大决定等核心变化，以及 AI 推测，会出现在审核中；确认后才写入已确认资料。'],
  ['日程：从整理结果中加入安排','例如「明天下午三点开会」，会在 AI 整理并校验时间后加入日程；发送后不会立即出现。可查看全部安排并标记完成。']
 ]},
 {mark:'05',title:'带着你的资料，使用其他 AI',lead:'按问题取相关背景，让不同的 AI 都能结合你的情况回答。',items:[
  ['最通用：复制问题和背景','打开「其他 AI」，输入准备问的问题，生成并复制相关背景，再粘贴到你使用的 AI。'],
  ['支持 MCP：复制连接配置','在「其他 AI」复制本机 MCP 配置，按对应客户端的方式接入。只查询已确认、允许分享的相关信息，不需要读取全部数据库。'],
  ['数据保存在你自己的电脑','设置中可打开数据文件夹、备份和导出。语言或模型切换不会重建档案；升级和卸载保留个人数据。']
 ],note:'之后可随时在「管理 → 设置 → 使用教程」重新查看。'}
];
let tutorialStep=0,tutorialFirstRun=false,tutorialBusy=false,tutorialReturnFocus=null;
function openTutorial(firstRun=false){
 const dialog=document.getElementById('tutorial');if(dialog.open)return;
 tutorialStep=0;tutorialFirstRun=firstRun;tutorialBusy=false;tutorialReturnFocus=document.activeElement;
 renderTutorial();dialog.showModal();document.getElementById('tutorial-next').focus({preventScroll:true});
}
function renderTutorial(){
 const page=tutorialPages[tutorialStep],last=tutorialStep===tutorialPages.length-1;
 const body=document.getElementById('tutorial-body');
 const languages=el('select',{id:'tutorial-language',ariaLabel:t('界面语言'),disabled:tutorialBusy},el('option',{value:'zh-CN',text:'中文（简体）'}),el('option',{value:'en',text:'English'}));languages.value=state.settings.language;
 languages.onchange=async()=>{
  if(tutorialBusy)return;tutorialBusy=true;languages.disabled=true;
  try{await api('/api/settings',{language:languages.value});await showView(currentView);}
  catch(error){toast(error.message);}
  finally{tutorialBusy=false;renderTutorial();}
 };
 const header=el('div',{className:'tutorial-header'},el('span',{className:'tutorial-brand',text:'M'}),el('span',{className:'eyebrow',text:t('使用教程')}));
 if(tutorialFirstRun)header.append(languages);
 header.append(button(tutorialFirstRun?t('稍后再看'):t('关闭'),finishTutorial,'subtle tutorial-dismiss'));
 const progress=el('div',{className:'tutorial-progress',ariaLabel:tf('第 {0} / {1} 步',tutorialStep+1,tutorialPages.length)},...tutorialPages.map((_,i)=>el('span',{className:i<=tutorialStep?'done':''})));
 const items=page.items.map(([title,description],i)=>el('article',{className:'tutorial-item'},
  el('span',{className:'tutorial-item-index',text:String(i+1)}),
  el('div',{},el('h3',{text:t(title)}),el('p',{text:t(description)}))));
 const content=el('div',{className:'tutorial-content'},
  el('span',{className:'tutorial-number',text:page.mark}),el('h2',{id:'tutorial-title',text:t(page.title)}),
  el('p',{className:'tutorial-lead',text:t(page.lead)}),el('div',{className:'tutorial-items'},...items));
 if(page.note)content.append(el('p',{className:'tutorial-note',text:t(page.note)}));
 const back=button(t('上一步'),()=>{tutorialStep--;renderTutorial();},'subtle');back.id='tutorial-back';back.disabled=tutorialBusy||tutorialStep===0;
 const next=button(last?(tutorialFirstRun?t('开始填写档案'):t('完成')):t('下一步'),async()=>{if(last)await finishTutorial();else{tutorialStep++;renderTutorial();}},'primary');next.id='tutorial-next';next.disabled=tutorialBusy;
 const footer=el('footer',{className:'tutorial-actions'},back,el('small',{className:'muted',text:tf('第 {0} / {1} 步',tutorialStep+1,tutorialPages.length)}),next);
 body.replaceChildren(header,progress,content,footer);
 for(const node of body.querySelectorAll('button'))if(tutorialBusy)node.disabled=true;
}
async function finishTutorial(){
 if(tutorialBusy)return;tutorialBusy=true;renderTutorial();
 try{
  if(tutorialFirstRun){await api('/api/settings',{tutorial_seen:true});await refreshState();}
  const startProfile=tutorialFirstRun&&!state.settings.onboarding_complete;
  document.getElementById('tutorial').close();
  if(startProfile)await openWizard();else if(tutorialReturnFocus?.isConnected)tutorialReturnFocus.focus({preventScroll:true});
 }finally{tutorialBusy=false;if(document.getElementById('tutorial').open)renderTutorial();}
}
document.getElementById('tutorial').addEventListener('cancel',event=>{event.preventDefault();finishTutorial().catch(error=>toast(error.message));});
function appendTutorialSettings(){
 view.append(el('section',{className:'card',id:'tutorial-settings'},el('h3',{text:t('使用教程')}),el('p',{className:'muted',text:t('随时重看记录、AI 整理、档案审核、日程和其他 AI 的使用方法。')}),button(t('打开使用教程'),()=>openTutorial(),'primary')));
}

async function init(){if(new URLSearchParams(location.search).has('compact'))document.body.classList.add('compact');await showView(['chat','profile','journal','memory','connect','settings','agenda'].includes(location.hash.slice(1))?location.hash.slice(1):'chat');if(!state.settings.onboarding_complete){if(!state.settings.tutorial_seen)openTutorial(true);else await openWizard();}refreshTimer=setTimeout(pollState,2000);}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollState();});
window.addEventListener('focus',()=>pollState());
init().catch(e=>{view.replaceChildren(empty(t("暂时无法连接"),e.message));});


async function appendAIConnectionSettings(){
 const info=await api('/api/web-ai');if(currentView!=='settings')return;
 const form=el('form',{id:'ai-connection-settings',className:'card'});form.onsubmit=e=>e.preventDefault();
 const mode=el('select',{name:'ai_mode',ariaLabel:t("AI 接入方式"),value:state.settings.ai_mode});
 mode.append(el('option',{value:'api',text:t("API 自动模式")}),el('option',{value:'web',text:t("网页版 AI（无需 API 密钥）")}));mode.value=state.settings.ai_mode;
 const platform=el('select',{name:'web_provider',ariaLabel:t("网页 AI 平台")});for(const [id,p] of Object.entries(info.providers))platform.append(el('option',{value:id,text:t(p.name)}));platform.value=state.settings.web_provider;
 const platformField=el('label',{className:'form-label'},t("网页 AI 平台"),platform);
 const note=el('p',{className:'muted',text:t("网页模式由你在官网发送并复制回复，软件校验后自动更新档案。账户登录、验证码和免费额度在官网处理。切换方式保留原来的 API 配置和全部个人资料。")});
 const toggle=()=>{platformField.hidden=mode.value!=='web';note.hidden=mode.value!=='web';};mode.onchange=toggle;toggle();
 form.append(el('h3',{text:t("AI 接入方式")}),el('label',{className:'form-label'},t("AI 接入方式"),mode),platformField,note,button(t("保存接入方式"),async()=>{
  await api('/api/settings',{ai_mode:mode.value,web_provider:platform.value});webDraft=null;await showView('settings');toast(mode.value==='web'?t("已启用网页模式，无需 API 密钥。"):t("已切回 API 模式，原有配置继续使用。"));
 },'primary'));view.append(form);
 if(!info.active)return;
 const platformInfo={...info.providers[info.selected],name:t(info.providers[info.selected].name)};
 if(webDraft&&webDraft.provider!==info.selected)webDraft=null;
 const flow=el('section',{id:'web-ai-flow',className:'card web-ai-flow'});view.append(flow);
 const openWebsite=async()=>{await api('/api/web-ai/open',{provider:info.selected});toast(t("已打开 ")+platformInfo.name+t(" 官网；请在浏览器登录。"));};
 function render(){
  flow.replaceChildren(el('h3',{text:t("用 ")+platformInfo.name+t(" 网页整理")}),el('p',{className:'muted',text:tf("{0} 条可分享输入等待整理。只打包本次输入和少量相关档案；成功后清除本地原文，核心变化仍需审核。",info.pending_inputs)}));
  const prepare=button(t("准备并复制整理内容"),async()=>{
   prepare.disabled=true;try{webDraft={...(await api('/api/web-ai/prepare',{})),reply:''};render();await copyText(webDraft.prompt);toast(t("整理内容已复制，打开 ")+platformInfo.name+t(" 后粘贴发送。"));}finally{prepare.disabled=false;}
  },'primary');
  flow.append(el('div',{className:'button-row'},prepare,button(t("打开 ")+platformInfo.name+t(" 网页"),openWebsite),el('a',{href:platformInfo.url,target:'_blank',rel:'noreferrer',text:t("官网链接")})),el('p',{className:'muted web-steps',text:t("① 准备并复制 → ② 在网页粘贴发送 → ③ 把完整 JSON 回复粘贴到下面并应用")}));
  if(webDraft){
   flow.append(el('p',{className:'muted',text:tf("本次准备 {0} 段输入{1}。整理内容有效期一小时，重开软件后请重新准备。",webDraft.source_count,webDraft.partial?t("；这批完成后还有后续分段"):'')}));
   const preview=el('details',{className:'web-preview'},el('summary',{text:t("查看将发给网页 AI 的整理内容")}),el('textarea',{className:'context-preview',readOnly:true,value:webDraft.prompt,ariaLabel:t("网页整理内容")}),button(t("再次复制整理内容"),()=>copyText(webDraft.prompt)));
   flow.append(preview);
  }
  const reply=el('textarea',{id:'web-ai-reply',value:webDraft?.reply||'',maxLength:120000,placeholder:t("粘贴网页 AI 返回的完整 JSON，可以包含 ```json 代码块。"),oninput:e=>{if(webDraft)webDraft.reply=e.target.value;}});
  const apply=button(t("校验并更新档案"),async()=>{
   if(!webDraft)throw new Error(t("请先准备整理内容，再到网页发送。"));apply.disabled=true;
   try{const result=await api('/api/web-ai/apply',{request_id:webDraft.request_id,reply:reply.value});webDraft=null;await showView('settings');toast(t("已更新档案并清除本地原文")+(result.pending_reviews?tf("；{0} 项核心变化待审核。",result.pending_reviews):'。'));}finally{apply.disabled=false;}
  },'primary');apply.disabled=!webDraft;reply.disabled=!webDraft;
  flow.append(el('label',{className:'form-label'},t("网页 AI 的整理回复"),reply),el('div',{className:'button-row'},apply),el('p',{className:'muted',text:t("格式错误或缺少原文依据时，保留输入并提示重试。网页登录信息由浏览器管理；网页聊天历史需在对应官网管理。网页模式暂停自动 API 整理、AI 回顾和语义 API 调用，存储维护照常运行。")}));
 }
 render();
}

async function copyText(text){try{await navigator.clipboard.writeText(text);}catch(error){const area=el('textarea',{value:text});document.body.append(area);area.select();const copied=document.execCommand('copy');area.remove();if(!copied)throw new Error(t("请选中预览文字后手动复制。"));}toast(t("已复制，可粘贴到其他 AI。"));}
function bytes(value){return value>=1024**3?(value/1024**3).toFixed(2)+' GB':value>=1024**2?(value/1024**2).toFixed(2)+' MB':(value/1024).toFixed(1)+' KB';}
async function renderConnections(){
 const config=await api('/api/integration');if(currentView!=='connect')return;
 const question=el('textarea',{id:'context-question',placeholder:t("准备向其他 AI 问什么？例如：结合我的情况，帮我安排学习计划。"),maxLength:2000});
 const output=el('div',{id:'context-output'});
 const generate=button(t("生成相关背景"),async()=>{generate.disabled=true;try{const found=await api('/api/context',{question:question.value});const packageText=t("我的问题：")+found.question+'\n\n'+found.context+t("\n请结合这些资料回答；资料未说明的情况请询问，不要推测。");const preview=el('textarea',{id:'context-preview',value:packageText,readOnly:true,className:'context-preview'});output.replaceChildren(el('p',{className:'muted',text:tf("找到 {0} 条资料 · 背景 {1}/{2} 字符",found.sources.length,found.chars,found.max_chars)+(found.truncated?t(" · 需要时可展开详情"):'')}),preview,button(t("复制问题和背景"),()=>copyText(packageText),'primary'));if(found.warning)output.append(el('p',{className:'muted',text:found.warning}));if(found.index_pending)output.append(el('p',{className:'muted',text:t("其余资料正在建立索引，稍后可再次检索。")}));for(const source of found.sources)output.append(button('#'+source.id+' '+source.title,async()=>{const data=await api('/api/context/sources',{ids:[source.id]});modal(t("检索来源"),el('div',{},el('div',{className:'raw-text',text:data.context}),button(t("复制这段信息"),()=>copyText(data.context))));},'subtle'));}finally{generate.disabled=false;}},'primary');
 const background=el('section',{className:'card'},el('h3',{text:t("为这个问题准备个人背景")}),el('p',{className:'muted',text:t("只取相关、已确认且允许分享的资料。可以预览后复制给任何 AI，默认检索不调用 AI；开启语义检索时会调用选定的 Embedding 服务。")}),question,generate,output);
 const stdio=JSON.stringify(config.stdio,null,2);const local=el('section',{className:'card'},el('h3',{text:t("让支持 MCP 的 AI 直接查询")}),el('p',{className:'muted',text:t("本机 MCP 客户端可使用下面的配置，例如 Claude Desktop、Cursor、Gemini CLI。每个客户端的配置入口不同，详见项目内的《其他AI接入说明》。只提供查询背景与展开详情两个工具。")}),el('pre',{text:stdio}),button(t("复制本机 MCP 配置"),()=>copyText(stdio)),el('p',{className:'muted',text:t("连接后可这样提问：先查询 personal-memory，再结合相关资料回答我的问题。")}));
 const http=el('section',{className:'card'},el('h3',{text:t("通过 MCP / HTTP 接口查询")}),el('p',{className:'muted',text:t("本机地址：")+config.mcp_url+t("。HTTP 查询需要独立访问密钥，可随时关闭；这个密钥与聊天 API 密钥分开。")}),el('span',{className:'badge',text:config.enabled?t("HTTP 访问已启用"):t("HTTP 访问已关闭")}),el('div',{className:'button-row'},button(config.enabled?t("重新生成访问密钥"):t("启用并生成访问密钥"),async()=>{const result=await api('/api/integration/key',{});const badge=http.querySelector('.badge');badge.textContent=t("HTTP 访问已启用");config.enabled=true;const input=el('input',{type:'password',value:result.key,readOnly:true});const settings=JSON.parse(JSON.stringify(config.http));settings.mcpServers['personal-memory'].headers.Authorization='Bearer '+result.key;modal(t("保存这次生成的访问密钥"),el('div',{},el('p',{className:'muted',text:t("仅在这里显示。重新生成后，旧密钥失效。")}),input,button(t("复制访问密钥"),()=>copyText(result.key)),button(t("复制带密钥的 MCP 配置"),()=>copyText(JSON.stringify(settings,null,2)))));}),button(t("关闭 HTTP 访问"),async()=>{await api('/api/integration/disable',{});await showView('connect');toast(t("HTTP 访问已关闭。"));},'subtle')),el('pre',{text:JSON.stringify(config.http,null,2)}),button(t("复制 HTTP 配置模板"),()=>copyText(JSON.stringify(config.http,null,2))),el('p',{className:'muted',text:t("备用 API：")+config.api_url+t("；接口定义：")+config.openapi_url}));
 const web=el('section',{className:'card'},el('h3',{text:t("连接云端网页 AI")}),el('p',{text:t("网页版 AI 需要能访问的连接通道。ChatGPT 可使用 Secure MCP Tunnel 连接上面的 stdio 服务；其他支持远程 MCP 的网页可使用带认证的 HTTPS 转发。对外连接需另行配置，数据库仍保存在本机。"),className:'muted'}),el('p',{text:t("没有自定义接口入口的网页，使用上方“生成相关背景”即可。支持 MCP 不代表所有网页都开放自定义连接，请根据所用平台配置。"),className:'muted'}));
 view.replaceChildren(background,local,http,web);
}
function appendMaintenanceSettings(){
 const controls=el('form',{id:'maintenance-settings',className:'card'});controls.onsubmit=e=>e.preventDefault();
 controls.append(el('h3',{text:t("自动整理与 API 使用")}),choiceField('organize_interval',t("集中整理周期"),[[600,t("每 10 分钟")],[1800,t("每半小时")],[3600,t("每小时（推荐）")],[43200,t("每半天")],[86400,t("每天")]],state.settings.organize_interval),el('p',{className:'muted',text:state.settings.ai_mode==='web'?t("网页版 AI 需在上方准备并回填，自动周期仅用于 API 模式。"):t("从第一条待整理记录开始计时；新记录加入同一批，不会把时间越推越晚。没有新记录不调用；积压较多时分批处理，重开后到期内容会继续整理。")}),choiceField('organize_tokens',t("每批整理最多输出（token）"),[[2000,t("2000 · 少量记录")],[4000,t("4000 · 推荐")],[8000,t("8000 · 较多记录")]],state.settings.organize_tokens),choiceField('daily_call_limit',t("每天最多 API 调用次数"),[[20,t("20 次")],[50,t("50 次")],[100,t("100 次")],[200,t("200 次")],[500,t("500 次")]],state.settings.daily_call_limit),choiceField('context_chars',t("每次发送给 AI 的文字预算（字符）"),[[6000,t("6000 · 精简")],[12000,t("12000 · 默认")],[24000,t("24000 · 较多信息")]],state.settings.context_chars),choiceField('retrieval_chars',t("提供给其他 AI 的相关背景预算（字符）"),[[600,'600'],[1800,t("1800 · 默认")],[3000,'3000'],[6000,'6000']],state.settings.retrieval_chars),el('p',{className:'muted',id:'api-usage',text:tf("今日 {0} 次 API 调用 · 服务报告共 {1} token。输出上限只限制返回长度；实际用量包括提示词、输入、相关资料与输出，以所用服务返回为准。调用次数含整理、回顾、连接测试与语义检索。",state.usage.calls,state.usage.tokens)}),el('p',{className:'muted',text:t("发送后只本地记录并显示成功提示，AI 仅用于定时提取与更新数据库。成功提取后清除原文；核心变化与 AI 推测仍由你审核。输出被截断时保留输入，提示调整上限后重试。API 预算耗尽时仍可记录，整理等待预算恢复。")}),check('autostart',t("开机启动桌面小窗"),state.settings.autostart),button(t("保存维护设置"),async()=>{const values=formValues(controls);for(const k of ['organize_interval','organize_tokens','daily_call_limit','context_chars','retrieval_chars'])values[k]=Number(values[k]);await api('/api/settings',values);await refreshState();toast(t("维护设置已保存。"));},'primary'));
 if(state.settings.ai_mode==='web')for(const name of ['organize_interval','organize_tokens','daily_call_limit'])controls.elements[name].disabled=true;
 view.append(controls);
}

async function appendStorageSettings(){
 const stats=await api('/api/storage');if(currentView!=='settings')return;
 const card=el('section',{className:'card'},el('h3',{text:t("空间与数据保护")}),el('p',{className:'muted',text:tf("数据库 {0} · 备份 {1} · 可重建缓存 {2} · 待整理 {3} 条 · 核心待审核 {4} 条 · 已压缩 {5} 条",bytes(stats.database_bytes),bytes(stats.backup_bytes),bytes(stats.cache_bytes),stats.pending_inputs,stats.core_reviews,stats.compressed_entries)}),el('p',{className:'muted',text:t("个人数据库没有人为容量上限，可以持续新增资料；上方显示实际占用。整理成功后清除原文，只保存关键信息。较早资料和档案历史可无损压缩，自动维护只清理可重建缓存并轮换自动备份，保留至少一份。手动与升级备份可在备份列表管理。")}),button(t("现在整理存储空间"),async()=>{await api('/api/storage/maintain',{});await showView('settings');toast(t("已清理可重建缓存并处理无损压缩。"));}),el('a',{href:'/export?compress=1',download:'personal-export.json.gz',text:t("导出压缩版全部数据")}),button(t("查看内置提示词"),async()=>{const prompts=await api('/api/prompts');modal(t("内置处理规则"),el('div',{},...Object.entries(prompts).flatMap(([name,text])=>[el('h3',{text:name}),el('pre',{text})])));},'subtle'));
 if(stats.warning)card.append(el('p',{className:'danger',text:t("磁盘可用空间不足 2 GB，可检查备份占用或迁移保存位置。")}));
 const maintenance=el('form',{});maintenance.onsubmit=e=>e.preventDefault();maintenance.append(el('p',{className:'muted',text:t("这些选项只控制自动备份与可重建缓存的占用，不限制个人数据库。")}),choiceField('auto_backup_mb',t("自动备份保留空间（MB）"),[[128,'128'],[256,t("256 · 默认")],[512,'512'],[1024,'1024']],state.settings.auto_backup_mb),choiceField('cache_mb',t("可重建缓存保留空间（MB）"),[[16,'16'],[32,t("32 · 默认")],[64,'64']],state.settings.cache_mb),choiceField('compress_after_days',t("历史资料多久后可无损压缩"),[[90,t("90 天")],[180,t("180 天 · 默认")],[365,t("一年")]],state.settings.compress_after_days),button(t("保存空间维护设置"),async()=>{const values=formValues(maintenance);for(const k of ['auto_backup_mb','cache_mb','compress_after_days'])values[k]=Number(values[k]);await api('/api/settings',values);await refreshState();toast(t("空间维护设置已保存。"));},'subtle'));
 card.append(el('details',{},el('summary',{text:t("缓存与备份维护选项")}),maintenance));view.append(card);
 const providers=await api('/api/providers');const selected=el('select',{name:'embedding_provider'});selected.append(el('option',{value:'',text:t("选择语义检索服务")}));for(const p of providers)selected.append(el('option',{value:p.id,text:p.name,selected:p.id===state.settings.embedding_provider}));
 const form=el('form',{className:'card'});form.onsubmit=e=>e.preventDefault();form.append(el('h3',{text:t("语义检索（可选）")}),check('semantic_enabled',t("启用意思相近的资料检索"),state.settings.semantic_enabled),el('label',{className:'form-label'},t("独立选择语义服务"),selected),field('embedding_model',t("Embedding 模型 ID"),'text',state.settings.embedding_model),el('p',{className:'muted',text:t("默认关闭，关键词与主题检索可以直接使用。开启后，允许分享的资料片段和查询会发送到这里选定的服务 /embeddings 接口，计入每日调用次数。向量缓存可重建；切换聊天模型不会改变它。")}),button(t("保存语义检索设置"),async()=>{const values=formValues(form);if(values.semantic_enabled&&(!values.embedding_provider||!values.embedding_model))throw new Error(t("请先选择服务并填写 Embedding 模型 ID。"));await api('/api/settings',values);await refreshState();toast(t("语义检索设置已保存。"));},'primary'));view.append(form);
}

function applyAppearance(palette){
 if(!palette)return;
 const mapping={bg:'bg',paper:'paper',ink:'ink',muted:'muted',accent:'green',line:'line',soft:'soft',hover:'hover',button_ink:'button-ink'};
 for(const [key,name] of Object.entries(mapping))document.documentElement.style.setProperty('--'+name,palette[key]);
}
function colourMix(a,b,t){return '#'+[1,3,5].map(i=>Math.round(parseInt(a.slice(i,i+2),16)*(1-t)+parseInt(b.slice(i,i+2),16)*t).toString(16).padStart(2,'0')).join('');}
function colourLum(c){const values=[1,3,5].map(i=>parseInt(c.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return values[0]*.2126+values[1]*.7152+values[2]*.0722;}
async function appendAppearanceSettings(){
 const config=await api('/api/appearance');if(currentView!=='settings')return;
 const form=el('form',{id:'appearance-settings',className:'card appearance-settings'});form.onsubmit=e=>e.preventDefault();
 const preset=el('input',{type:'hidden',name:'theme_preset',value:state.settings.theme_preset});
 const picks=el('div',{className:'appearance-presets'}),inputs={},hexLabels={},choices={};
 const preview=el('div',{className:'appearance-preview'},el('div',{className:'preview-header'},el('strong',{text:t("● 拾记")}),el('span',{text:t("管理　固定")})),el('div',{className:'preview-agenda'},el('strong',{text:t("日程")}),el('p',{text:t("○　明天 15:00 · 项目会议")}),el('p',{text:t("○　待办 · 整理工作计划")})),el('div',{className:'preview-card preview-inline'},el('span',{text:t("想到什么就写下来…")}),el('small',{text:t("✓ AI 整理")}),el('span',{className:'preview-send',text:t("发送")})));
 const colours=el('div',{className:'appearance-colours'});
 function updatePreview(){
  const bg=inputs.theme_bg.value,accent=inputs.theme_accent.value,text=inputs.theme_text.value;
  for(const key of Object.keys(inputs))hexLabels[key].textContent=inputs[key].value.toUpperCase();
  preview.style.setProperty('--preview-bg',bg);preview.style.setProperty('--preview-accent',accent);preview.style.setProperty('--preview-ink',text);
  preview.style.setProperty('--preview-paper',colourMix(bg,'#ffffff',colourLum(bg)<.3?.05:.8));preview.style.setProperty('--preview-muted',colourMix(bg,text,.6));preview.style.setProperty('--preview-line',colourMix(bg,text,.15));
  const contrast=(a,b)=>(Math.max(colourLum(a),colourLum(b))+.05)/(Math.min(colourLum(a),colourLum(b))+.05);
  preview.style.setProperty('--preview-button-ink',contrast(accent,'#ffffff')>=contrast(accent,'#17251d')?'#ffffff':'#17251d');
  for(const [key,node] of Object.entries(choices)){node.classList.toggle('active',preset.value===key);node.setAttribute('aria-pressed',String(preset.value===key));}
 }
 function choose(key){preset.value=key;if(config.presets[key])for(const name of Object.keys(inputs))inputs[name].value=config.presets[key][name];updatePreview();}
 for(const [key,title] of [['theme_bg',t("背景颜色")],['theme_accent',t("主题色")],['theme_text',t("文字颜色")]]){
  inputs[key]=el('input',{type:'color',name:key,ariaLabel:title,value:state.settings[key],oninput:()=>{preset.value='custom';updatePreview();}});
  hexLabels[key]=el('small',{text:state.settings[key]});colours.append(el('label',{className:'colour-control'},el('span',{text:title}),inputs[key],hexLabels[key]));
 }
 for(const [key,item] of [...Object.entries(config.presets),['custom',{label:t("自定义")}]]){choices[key]=button(t(item.label),()=>choose(key));picks.append(choices[key]);}
 const save=async()=>{await api('/api/settings',formValues(form));await refreshState();toast(t("配色已保存，小窗和大窗口同步使用。"));};
 form.append(el('h3',{text:t("外观与颜色")}),el('p',{className:'muted',text:t("常驻小窗约 360 × 240；档案、设置和审核在较大的窗口中打开。选一套配色，或调整下面的颜色；保存后小窗立即更新。")}),preset,picks,el('div',{className:'appearance-layout'},preview,colours),el('div',{className:'button-row'},button(t("保存配色"),save,'primary'),button(t("恢复默认配色"),async()=>{choose('paper');await save();},'subtle')));
 view.append(form);choose(preset.value);
}
window.addEventListener('hashchange',()=>{const selected=location.hash.slice(1);if(['chat','profile','journal','memory','settings','connect','agenda'].includes(selected)&&selected!==currentView)showView(selected).catch(e=>toast(e.message));});


function appendLanguageSettings(){
 const card=el('section',{className:'card',id:'language-settings'});
 const select=el('select',{id:'interface-language',ariaLabel:t('界面语言')},el('option',{value:'zh-CN',text:'中文（简体）'}),el('option',{value:'en',text:'English'}));select.value=state.settings.language;
 select.onchange=async()=>{
  select.disabled=true;
  const providerSelection=document.getElementById('provider-select')?.value;
  const drafts=[...view.querySelectorAll('form')].filter(f=>f.id).map(form=>[form.id,formValues(form)]);
  try{
   await api('/api/settings',{language:select.value});await showView('settings');
   const providerSelect=document.getElementById('provider-select');if(providerSelect&&providerSelection!==undefined){providerSelect.value=providerSelection;providerSelect.dispatchEvent(new Event('change'));}
   for(const [id,values] of drafts){const form=document.getElementById(id);if(!form)continue;for(const input of form.elements){if(input.name in values){if(input.type==='checkbox')input.checked=values[input.name];else input.value=values[input.name];}}}
   toast(t('语言已更新。'));
  }finally{select.disabled=false;}
 };
 card.append(el('h3',{text:t('语言')}),el('label',{className:'form-label'},t('界面语言'),select),el('p',{className:'muted',text:t('语言只改变界面显示，不翻译或改写你的个人资料。')}));view.append(card);
 const about=el('section',{className:'card',id:'about-meology'},el('h3',{text:t('关于')+' Meology'}),el('p',{text:(state.settings.language==='en'?'Meology':'拾记 · Meology')+' V'+state.version.replace(/\.0$/,'')}),el('small',{className:'muted',text:t('数据文件夹')+': '+state.data_folder}),button(t('打开数据文件夹'),()=>api('/api/data-folder/open',{}),'subtle'));view.append(about);
}
