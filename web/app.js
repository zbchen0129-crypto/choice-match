'use strict';
const $ = id => document.getElementById(id);
const topics = {video_calls:'视频会议网络', quiet:'夜间安静', workspace:'工作桌椅', parking:'停车条件', laundry:'洗衣条件'};
const labels = {support:'有支持证据',risk:'存在风险',mixed:'正反证据并存',unknown:'信息不足',pass:'已知满足',fail:'不满足'};
const fields = {bedrooms:'卧室数量',cats_allowed:'养猫规则',monthly_budget:'每月总预算'};
let baseResult = null, userDecisions = {};
let config = {}, result = null, bucket = 'eligible', selected = new Set(), busy = false, unhandled = [];
function el(tag, cls, text) { const node = document.createElement(tag); if(cls) node.className = cls; if(text !== undefined) node.textContent = text; return node; }
function money(cents) { return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(cents/100); }
function total(row) { return row.monthly_costs.items.reduce((n,item)=>n+(item.amount_cents??0),0); }
function completeCost(row) { return row.monthly_costs.complete && row.monthly_costs.items.every(item=>item.amount_cents!==null); }
function message(text,error=false) { $('message').textContent=text; $('message').classList.toggle('error',error); }
async function api(path,body) { const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const data=await response.json(); if(!response.ok) throw new Error(data.error || '请求失败'); return data; }
function lock(value) { busy=value; document.querySelectorAll('.requirements input,.requirements select,.requirements textarea,.requirements button').forEach(n=>n.disabled=value); $('parse').disabled=value||!config.model_configured; $('rag').disabled=value||!config.model_configured||unhandled.length>0; if(!config.historical_available) $('dataset').querySelector('[value="historical"]').disabled=true; }
function requirements() {
  const hard=[];
  if($('bedrooms').value!=='') hard.push(['bedrooms','gte',Number($('bedrooms').value)]);
  if($('cats').checked) hard.push(['cats_allowed','eq',true]);
  const preferences={}; Object.keys(topics).forEach(t=>{if(Number($('pref-'+t).value)) preferences[t]=Number($('pref-'+t).value);});
  return {hard,preferences,monthly_budget_cents:$('budget').value===''?null:Math.round(Number($('budget').value)*100),unhandled_requirements:unhandled};
}
function showUnhandled(items) { unhandled=items; $('unhandled').hidden=!items.length; $('unhandled-text').textContent='当前未支持或尚需澄清：'+items.join('；'); lock(busy); }
function setRequirements(req) {
  const bed=req.hard.find(c=>c[0]==='bedrooms');
  if(bed && !$('bedrooms').querySelector(`option[value="${bed[2]}"]`)) { const option=el('option','',String(bed[2])); option.value=bed[2]; $('bedrooms').append(option); }
  $('bedrooms').value=bed?String(bed[2]):''; $('cats').checked=req.hard.some(c=>c[0]==='cats_allowed'&&c[2]===true);
  $('budget').value=req.monthly_budget_cents===null?'':req.monthly_budget_cents/100;
  Object.keys(topics).forEach(t=>$('pref-'+t).value=String(req.preferences[t]||0)); showUnhandled(req.unhandled_requirements||[]);
}
function datasetNote() { $('data-note').textContent=$('dataset').value==='demo'?'所有房源、评论、费用和日期均为虚构，用于展示决策流程。':'2019 年 12 月的历史广告；不表示当前可租，广告描述也不是住客体验。'; }
function invalidate() { baseResult=null; userDecisions={}; $('evidence-dialog').close(); result=null; selected.clear(); $('cards').replaceChildren(); $('empty').hidden=true; $('compare-panel').hidden=true; $('export').disabled=true; document.querySelectorAll('.tabs span').forEach(n=>n.textContent='—'); $('result-note').textContent=''; message('条件已修改。点击“更新候选”查看新的结果。'); }
async function compare(mode='rules') {
  if(busy) return;
  if(!$('budget').checkValidity()) { $('budget').reportValidity(); return; }
  if(unhandled.length) { message('请先处理上方标出的未支持需求。',true); return; }
  $('evidence-dialog').close(); baseResult=null; userDecisions={}; $('export').disabled=true; lock(true); message(mode==='model'?'正在检索证据并生成解释，可能需要几分钟…':'正在按条件筛选候选…');
  try {
    result=await api(mode==='model'?'/api/rag':'/api/compare',{dataset:$('dataset').value,requirements:requirements(),original_query:$('request').value});
    userDecisions={};
    result.request={dataset:$('dataset').value,requirements:requirements(),original_query:$('request').value}; baseResult=structuredClone(result); selected.clear();
    if(!result.comparison[bucket].length) bucket=result.comparison.eligible.length?'eligible':result.comparison.needs_verification.length?'needs_verification':'excluded';
    render(); $('export').disabled=false;
    message(mode==='model'?(result.truncated?`已分析检索选出的 ${result.candidate_count_considered} 个候选；另有候选未深入分析。解释引用已检查，语义仍需核对。`:'AI 分析完成。解释引用已检查，语义仍需核对。'):($('dataset').value==='demo'?'基于虚构样例的规则比较。切换“远程办公 / 休假模式”，观察需求如何改变排序。':'历史广告筛选完成。额外月费未确认，因此预算内的广告仍可能进入“待核实”。'));
  } catch(error) { result=null; $('cards').replaceChildren(); $('compare-panel').hidden=true; $('export').disabled=true; message(error.message,true); }
  finally { lock(false); }
}
function render() {
  document.querySelectorAll('[data-bucket]').forEach(button=>{button.classList.toggle('active',button.dataset.bucket===bucket);button.querySelector('span').textContent=result.comparison[button.dataset.bucket].length;});
  const rows=result.comparison[bucket]; $('cards').replaceChildren(); $('empty').hidden=rows.length>0;
  $('result-note').textContent=({eligible:'“已知满足”仅指列出的硬条件；偏好中的风险与未知仍需查看。',needs_verification:'有硬条件尚未确认。缺失信息不会被当作满足。',excluded:'包含硬条件不满足或你主动排除的房源；可查看依据，用户排除可以撤销。'})[bucket]+' 当前使用透明规则排序；同分按 ID 排列。';
  rows.forEach((row,i)=>$('cards').append(card(row,i))); renderComparison();
}
function card(row,index) {
  const node=el('article','card'); const top=el('div','card-top'), title=el('div','card-title'); title.append(el('span','rank',String(index+1).padStart(2,'0')));
  const name=el('div'); name.append(el('h3','',row.name),el('div','metadata',`${row.attributes.bedrooms??'未知'} 间卧室 · ${row.historical?'历史广告 / 2019':'虚构演示'} · ${row.id}`)); title.append(name);
  const price=el('div','price',`${completeCost(row)?'':'≥ '}${money(total(row))}`); price.append(el('small','',completeCost(row)?'已知总费用 / 月':'已知费用下界 / 月')); top.append(title,price); node.append(top);
  const tags=el('div','tags'); row.checks.forEach(check=>tags.append(el('span','tag '+check.status,`${fields[check.field]||check.field} · ${labels[check.status]}`))); node.append(tags);
  const summary=row.evidence_summary; if(summary) {const box=el('div','risk-summary');box.append(el('p','',`风险：${summary.risk_topics.map(t=>topics[t]).join('、')||'暂无记录（不代表没有风险）'}`),el('p','',`待核实：${summary.missing_topics.map(t=>topics[t]).join('、')||'仍需核对证据适用范围'}`));node.append(box);}
  if(userDecisions[row.id]) node.append(el('p','warning',`用户排除：${userDecisions[row.id].reason}（个人决定，非事实认证）`));
  const topicNodes=el('div','topics'); row.topics.forEach(topic=>{const t=el('div','topic'); t.append(el('strong','',`${topics[topic.topic]} · ${labels[topic.status]}`)); const first=topic.evidence[0]; t.append(el('p','',first?`${first.quote}${topic.evidence.length>1?`（另有 ${topic.evidence.length-1} 条证据）`:''}`:'尚未找到可用证据，不能据此判断条件良好。')); topicNodes.append(t);}); node.append(topicNodes);
  const claims=result.claims.filter(c=>c.candidate_id===row.id); if(claims.length) {const block=el('div','claims'); claims.forEach(c=>block.append(el('p','',`${c.text} [${c.source_ids.join(', ')}]`))); node.append(block);}
  const bottom=el('div','card-bottom'),label=el('label','checkbox'),checkbox=el('input'); checkbox.type='checkbox'; checkbox.checked=selected.has(row.id); checkbox.setAttribute('aria-label',`比较 ${row.name}`); checkbox.addEventListener('change',()=>{if(checkbox.checked){if(selected.size>=3){checkbox.checked=false;message('最多同时比较 3 个候选。',true);return;}selected.add(row.id);}else selected.delete(row.id);renderComparison();}); label.append(checkbox,document.createTextNode('加入比较'));
  const open=el('button','text-button','查看证据与缺口 ↗'); open.type='button'; open.addEventListener('click',()=>openEvidence(row)); bottom.append(label,open); node.append(bottom); return node;
}
function allRows() { return result?Object.values(result.comparison).flat():[]; }
function renderComparison() {
  const rows=allRows().filter(r=>selected.has(r.id)); $('compare-panel').hidden=!rows.length; $('comparison-table').replaceChildren(); if(!rows.length) return;
  const table=el('table'),header=el('tr'); header.append(el('th','','比较维度')); rows.forEach(r=>header.append(el('th','',r.name))); const head=el('thead');head.append(header);table.append(head);const body=el('tbody');
  const lines=[['费用 / 月',r=>`${completeCost(r)?'':'≥ '}${money(total(r))}${completeCost(r)?'':' · 不完整'}`],['硬条件',r=>r.checks.map(c=>`${fields[c.field]}：${labels[c.status]}`).join('；')],...Object.keys(requirements().preferences).map(t=>[topics[t],r=>labels[r.topics.find(x=>x.topic===t)?.status||'unknown']])];
  lines.forEach(([label,get])=>{const tr=el('tr');tr.append(el('th','',label));rows.forEach(r=>tr.append(el('td','',get(r))));body.append(tr);});table.append(body);$('comparison-table').append(table);
}
function openEvidence(row) {
  if(busy || !baseResult) return;
  $('evidence-title').textContent=row.name; const body=$('evidence-body');body.replaceChildren();
  body.append(el('p','help',row.historical?'历史广告中的描述来自发布者，不代表当前状态或经验证的住客体验。':'以下来源、日期和体验均为演示虚构。'));
  const costs=el('section','evidence');costs.append(el('h3','','费用与完整性'));
  row.monthly_costs.items.forEach(item=>costs.append(el('p','',`${({rent:'月租',advertised_rent:'广告月租',mandatory_monthly_fees:'额外月费',unverified_monthly_fees:'待核实月费'})[item.label]||item.label}：${item.amount_cents===null?'未知':money(item.amount_cents)} · 来源 ${item.source_id}`)));
  costs.append(el('p','',completeCost(row)?'样例标记为月度费用完整。':'仍有未核实月费；已知金额仅为下界。'));body.append(costs);
  row.topics.forEach(topic=>{const section=el('section','evidence');section.append(el('h3','',`${topics[topic.topic]} · ${labels[topic.status]}`));if(!topic.evidence.length)section.append(el('p','','暂无相关证据。预订或签约前需要另行核实。'));topic.evidence.forEach(e=>{section.append(el('p','metadata',`${e.source_id} · ${e.source.date} · ${labels[e.direction]}`),el('blockquote','',e.quote),el('p','',`适用条件与局限：${e.conditions}`));});body.append(section);});
  appendReviewControls(row,body);
  const sources=el('section','evidence');sources.append(el('h3','','原始来源'));
  Object.entries(row.sources).forEach(([sid,source])=>{const details=el('details');details.append(el('summary','metadata',`${sid} · ${source.date}`),el('blockquote','',source.text));if(source.fields) details.append(el('p','',JSON.stringify(source.fields)));sources.append(details);});body.append(sources); $('evidence-dialog').showModal();
}
Object.entries(topics).forEach(([key,name])=>{const div=el('div','preference'),label=el('label','',name);label.htmlFor='pref-'+key;const select=el('select');select.id='pref-'+key;['不考虑','一般偏好','重要','非常重要'].forEach((text,i)=>{const option=el('option','',text);option.value=i;select.append(option);});select.value=key==='video_calls'?'3':key==='quiet'?'2':'0';div.append(label,select);$('preferences').append(div);});
$('compare').addEventListener('click',()=>compare());$('rag').addEventListener('click',()=>compare('model'));
$('parse').addEventListener('click',async()=>{lock(true);invalidate();message('正在解析需求…');try{const req=await api('/api/parse',{text:$('request').value});setRequirements(req);message('需求已解析。请检查左侧条件，再更新候选。');}catch(e){message(e.message,true);}finally{lock(false);}});
['budget','bedrooms','cats',...Object.keys(topics).map(t=>'pref-'+t)].forEach(id=>$(id).addEventListener('change',invalidate));
$('dataset').addEventListener('change',()=>{datasetNote();invalidate();compare();});
$('drop-unhandled').addEventListener('click',()=>{$('request').value='';showUnhandled([]);invalidate();message('已明确移除未支持的限制。当前比较将只使用左侧条件。');});
['remote','vacation'].forEach(id=>$(id).addEventListener('click',()=>{$('request').value='';Object.keys(topics).forEach(t=>$('pref-'+t).value=t==='quiet'?'2':t==='video_calls'&&id==='remote'?'3':'0');invalidate();compare();}));
document.querySelectorAll('[data-bucket]').forEach(button=>button.addEventListener('click',()=>{bucket=button.dataset.bucket;if(result)render();}));
$('clear-compare').addEventListener('click',()=>{selected.clear();render();});$('close-dialog').addEventListener('click',()=>$('evidence-dialog').close());
$('export').addEventListener('click',()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='choicematch-comparison.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
(async()=>{datasetNote();try{config=await api('/api/status');$('model-note').textContent=config.model_configured?'模型已配置。解析和 AI 解释会调用付费 API；请先检查输入。':'模型尚未配置；你仍可手动调整条件，体验完整比较流程。';lock(false);await compare();}catch(e){message('无法连接本地服务：'+e.message,true);}})();

$('request').maxLength=4000;
$('request').addEventListener('input',invalidate);

function applyUserDecisions() {
  result=structuredClone(baseResult);
  for(const [id,decision] of Object.entries(userDecisions)) {
    for(const name of ['eligible','needs_verification']) {
      const i=result.comparison[name].findIndex(r=>r.id===id);
      if(i<0) continue;
      const row=result.comparison[name].splice(i,1)[0];
      row.recommendation_status='excluded'; row.exclusion_reasons.push(decision);
      result.comparison.excluded.push(row);
    }
  }
  result.claims=result.claims.filter(c=>!userDecisions[c.candidate_id]);
  result.user_exclusions=structuredClone(userDecisions);
  if('excluded' in result) result.excluded=structuredClone(result.comparison.excluded);
  selected.clear(); render();
}
function appendReviewControls(row,body) {
  const section=el('section','evidence review-controls');section.append(el('h3','','我的排除决定'));
  const decision=userDecisions[row.id];
  if(decision) {
    section.append(el('p','',`不能接受：${decision.unacceptable_condition}`),el('p','',`理由：${decision.reason}`));
    decision.citations.forEach(c=>section.append(el('p','metadata',c.source_id),el('blockquote','',c.quote)));
    const undo=el('button','secondary','撤销我的排除');undo.type='button';undo.addEventListener('click',()=>{delete userDecisions[row.id];applyUserDecisions();$('evidence-dialog').close();message('已撤销用户排除，恢复本次分析结果。');});section.append(undo);
  } else if(row.checks.some(c=>c.status==='fail')) {
    section.append(el('p','','这套房源因列出的硬条件不满足而排除。修改需求后可重新比较。'));
  } else {
    section.append(el('p','help','这是你的选择，不代表系统证实房源不合格。决定仅保留于本次结果；更新条件、重新分析或刷新页面会清除。'));
    const label1=el('label','','我不能接受的情况'),condition=el('input');condition.id='review-condition';condition.maxLength=1000;label1.htmlFor=condition.id;
    const label2=el('label','','选择依据原文'),source=el('select');source.id='review-source';label2.htmlFor=source.id;
    const choices=[];
    row.topics.forEach(t=>t.evidence.forEach(e=>{if(e.quote.length<=2000&&!choices.some(c=>c.source_id===e.source_id&&c.quote===e.quote))choices.push({source_id:e.source_id,quote:e.quote});}));
    Object.entries(row.sources).forEach(([id,value])=>{if(!choices.some(c=>c.source_id===id))choices.push({source_id:id,quote:value.text.slice(0,2000)});});
    choices.forEach((c,i)=>{const option=el('option','',c.source_id);option.value=i;source.append(option);});
    const quote=el('blockquote','',choices[0]?.quote||'暂无来源');source.addEventListener('change',()=>{quote.textContent=choices[Number(source.value)].quote;});
    const label3=el('label','','为什么这条材料让我排除它'),reason=el('textarea');reason.id='review-reason';reason.maxLength=1000;reason.rows=3;label3.htmlFor=reason.id;
    const error=el('p','error');error.setAttribute('role','status');
    const submit=el('button','primary','确认按此依据排除');submit.type='button';submit.disabled=!choices.length;
    submit.addEventListener('click',async()=>{
      if(!condition.value.trim()||!reason.value.trim()){error.textContent='请填写不能接受的情况和排除理由。';return;}
      const activeBase=baseResult;submit.disabled=true;error.textContent='正在核对来源…';
      try {
        const data=await api('/api/review-exclusion',{...activeBase.request,choice:{candidate_id:row.id,context_hash:row.review_context,unacceptable_condition:condition.value.trim(),reason:reason.value.trim(),citations:[choices[Number(source.value)]]}});
        if(baseResult!==activeBase)return;
        userDecisions[row.id]=data.decision;applyUserDecisions();$('evidence-dialog').close();message('已按你的决定排除。可在“已排除”中查看原因或撤销。');
      } catch(e){error.textContent=e.message;} finally {submit.disabled=false;}
    });
    section.append(label1,condition,label2,source,quote,label3,reason,error,submit);
  }
  body.append(section);
}
