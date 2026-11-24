'use strict';
const byId=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const percent=n=>(100*n).toFixed(1)+'%';
const names={'before-sunrise':'日出前会议','after-dinner':'晚餐后会议','fifteen-minutes':'十五分钟会议','six-hours':'六小时培训','weekend-sleep':'周末睡眠','weekday-sleep':'工作日睡眠','weekday-early-work':'工作日日出前会议与安静','weekend-evening-work':'周末晚餐后会议与安静'};
let data=null,alpha='0.2';
function render(){
 const c=data.cases.find(c=>c.id===byId('lab-case').value),v=c.variants[alpha];
 const docs=Object.fromEntries(data.documents.map(d=>[d.id,d]));
 const display=ids=>ids.length?ids.map(id=>`${docs[id].candidate} · ${id}`).join('；'):'无';
 byId('lab-query').textContent=c.query;
 byId('lab-topics').textContent='主题偏好：'+Object.entries(c.preferences).map(([t,w])=>`${t==='quiet'?'安静':'视频会议'} × ${w}`).join('，');
 byId('weight-description').textContent=`主题排名占 ${Math.round((1-Number(alpha))*100)}%，原问题排名占 ${Math.round(Number(alpha)*100)}%。仅改变本页实验结果。`;
 byId('case-metrics').replaceChildren();
 for(const [label,key] of [['场景证据召回','recall_at_k'],['场景风险召回','risk_recall_at_k'],['一般主题风险召回','general_topic_risk_recall_at_5']]){const box=node('div',undefined,'metric');box.append(node('span',label),node('strong',percent(v.metrics[key])));byId('case-metrics').append(box);}
 byId('lab-changes').replaceChildren(node('p','相对 α = 20%：'),node('p','进入前五名：'+display(v.entered)),node('p','退出前五名：'+display(v.exited)),node('p','新增相关证据：'+display(v.new_relevant)),node('p','新增风险证据：'+display(v.new_risks)),node('p','丢失的风险证据：'+display(v.displaced_risks),'lost'));
 byId('lab-candidates').replaceChildren();
 v.selected.forEach((id,index)=>{const d=docs[id],s=c.signals[id],card=node('article',undefined,'candidate');const head=node('header');head.append(node('h3',`${index+1}. 候选 ${d.candidate} · ${id}`),node('span','检索分 '+v.scores[id].toFixed(4),'score'));card.append(head);const tags=node('div',undefined,'tags');tags.append(node('span',c.relevant.includes(id)?'场景相关':'未标为场景相关','tag'));if(c.risks.includes(id))tags.append(node('span','场景风险','tag risk'));else if(c.general_topic_risks.includes(id))tags.append(node('span','一般主题风险','tag risk'));if(v.entered.includes(id))tags.append(node('span','新进入','tag'));card.append(tags,node('blockquote',d.text));const details=node('details');details.append(node('summary','查看分数组成'),node('p',`主题命中数 ${s.coverage.length}；主题排名信号 ${s.topic.toFixed(4)}；原问题排名信号 ${s.original.toFixed(4)}。`),node('p',`${(1-Number(alpha)).toFixed(1)} × ${s.topic.toFixed(4)} + ${Number(alpha).toFixed(1)} × ${s.original.toFixed(4)} = ${v.scores[id].toFixed(4)}。分数不是概率。`));card.append(details);byId('lab-candidates').append(card);});
 byId('lab-summary').replaceChildren();
 for(const weight of data.weights){const key=String(weight),s=data.summary[key],tr=node('tr',undefined,key===alpha?'selected':'');for(const value of [Math.round(weight*100)+'%',percent(s.recall_at_k),percent(s.risk_recall_at_k),percent(s.general_topic_risk_recall_at_5),s.cases_recall_down+' / 8',s.cases_losing_risks+' / 8'])tr.append(node('td',value));byId('lab-summary').append(tr);}
 const t=data.theme_vector_summary;byId('theme-baseline').textContent=`纯主题向量对照：场景召回 ${percent(t.recall_at_k)}，场景风险召回 ${percent(t.risk_recall_at_k)}，一般风险召回 ${percent(t.general_topic_risk_recall_at_5)}。下降和丢失均相对排名融合 α = 20%。`;
 byId('load-status').textContent=`离线结果已载入 · ${names[c.id]} · 原问题权重 ${Math.round(Number(alpha)*100)}% · 0 次模型调用`;
}
byId('lab-case').addEventListener('change',render);
byId('lab-export').addEventListener('click',()=>{const c=data.cases.find(c=>c.id===byId('lab-case').value);const blob=new Blob([JSON.stringify({scope:data.scope,provenance:data.provenance,alpha:Number(alpha),case:c.id,query:c.query,selected:c.variants[alpha],live_calls:0},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=node('a');a.href=url;a.download=`choicematch-lab-${c.id}-${alpha}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
(async()=>{try{const response=await fetch('/lab-data.json');if(!response.ok)throw new Error('数据不可用');const text=await response.text();if(text.length>500000)throw new Error('数据超出大小限制');data=JSON.parse(text);if(data.cases.length!==8||data.documents.length!==18)throw new Error('案例数量不符');for(const c of data.cases){const o=node('option',names[c.id]||c.id);o.value=c.id;byId('lab-case').append(o);}for(const w of data.weights){const label=node('label'),input=node('input');input.type='radio';input.name='lab-weight';input.value=String(w);input.checked=String(w)===alpha;input.addEventListener('change',()=>{alpha=input.value;render();});label.append(input,node('span',Math.round(w*100)+'%'));byId('weight-options').append(label);}byId('lab-case').disabled=false;byId('weight-controls').disabled=false;byId('lab-export').disabled=false;byId('lab-provenance').textContent='来源报告：'+data.provenance.trace_file;render();}catch(error){byId('load-status').textContent='实验加载失败：'+error.message;}})();
