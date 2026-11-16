import {datasets,reviewPackages} from '../api/entities.js';
import {downloadFile} from '../api/client.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,fmt,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {PackageStatus} from '../constants/enums.js';
const pick={datasetId:null,records:[],assets:new Set(),model:''};
const submitKeys={};
const uuid=()=>window.crypto&&crypto.randomUUID?crypto.randomUUID():'key-'+Date.now()+'-'+Math.random().toString(36).slice(2);
let currentId=null;
const chip=s=>'<span class="status pkg-'+esc(s)+'">'+esc(PackageStatus[s]||s)+'</span>';
const mark=v=>v===null||v===undefined?'—':(Number(v)===1?'失效 1':'在役 0');
const itemRows=items=>items.map(i=>({...i,failed:mark(i.failed),verdict:mark(i.verdict)}));
function itemColumns(admin){
 const cols=[{key:'seq',label:'序号'},{key:'alias',label:'包内别名'}];
 if(admin)cols.push({key:'asset',label:'部件资产号'});
 return cols.concat([{key:'model',label:'型号'},{key:'km',label:'观测里程'},{key:'failed',label:'原登记'},{key:'verdict',label:'外协判定'}]);
}
function createPanel(ds,vendors){
 if(!ds.length)return '<section class="panel"><div class="section-title"><h2>建立外协复核包</h2></div><p class="empty">请先在数据接入导入样本批次。</p></section>';
 const opts=ds.map(d=>'<option value="'+d.id+'"'+(Number(pick.datasetId)===d.id?' selected':'')+'>'+esc(d.name)+' · '+d.rows+' 条</option>').join('');
 if(!vendors.length)return '<section class="panel"><div class="section-title"><h2>建立外协复核包</h2></div><p class="empty">尚无外协账号可分配，请先登记 vendor 角色账号。</p></section>';
 const vopts=vendors.map(v=>'<option value="'+v.id+'">'+esc(v.name)+'（'+esc(v.email)+'）</option>').join('');
 return '<section class="panel"><div class="section-title"><h2>建立外协复核包</h2><span>选定样本后内容冻结</span></div><form id="package-form"><label>复核包名称<input name="name" required minlength="2" maxlength="160" value="外协复核 · 失效状态抽检"></label><div class="parameter-grid"><label>来源数据批次<select name="dataset_id" id="pick-dataset">'+opts+'</select></label><label>指定外协账号<select name="vendor_id" required>'+vopts+'</select></label></div><div class="picker"><div class="picker-bar"><select id="pick-model"><option value="">全部型号</option></select><button type="button" class="text-button" id="pick-all">全选筛选结果</button><button type="button" class="text-button" id="pick-none">清空</button><span id="pick-count">已选 '+pick.assets.size+' 件</span></div><div class="picker-list" id="pick-list"><p class="hint">正在加载样本…</p></div></div><button type="submit" class="primary">冻结样本并分配给外协</button><p class="hint">冻结后内容不再随原批次变化；每件分配包内别名，资产号映射仅负责人可查。每包 1–500 件。</p></form></section>';
}
function listPanel(list,selectedId,isVendor){
 const items=list.length?list.map(p=>'<button class="batch-item'+(selectedId===p.id?' on':'')+'" data-pkg="'+p.id+'"><strong>'+esc(p.name)+'</strong><span>'+chip(p.status)+' · 已判定 '+p.verdict_count+'/'+p.item_count+'</span><small>'+(isVendor?'':esc(p.vendor||'')+' · ')+'创建 '+date(p.created_at)+'</small></button>').join(''):'<p class="empty">'+(isVendor?'尚无分配给你的复核包。':'尚无复核包，请先建立。')+'</p>';
 return '<section class="panel"><div class="section-title"><h2>'+(isVendor?'分配给我的复核包':'复核包')+'</h2><span>'+list.length+' 个</span></div><div class="batch-list tall">'+items+'</div></section>';
}
function detailPanel(p,role){
 const isAdmin=role==='admin',isVendor=role==='vendor',terminal=p.status==='adopted'||p.status==='revoked';
 const dates=[['创建',p.created_at],['领取',p.claimed_at],['回传',p.submitted_at],['关闭',p.closed_at]].filter(x=>x[1]).map(x=>'<span>'+x[0]+' <strong>'+date(x[1])+'</strong></span>').join('');
 let actions='';
 if(isVendor&&p.status==='assigned')actions+='<button class="primary small" id="claim-pkg">领取复核包</button>';
 if((isVendor||isAdmin)&&!terminal)actions+='<button class="button small" id="download-pkg">下载复核表 CSV ↓</button>';
 if(isAdmin&&p.status==='submitted')actions+='<button class="primary small" id="adopt-pkg">采纳回传并生成新批次</button>';
 if(isAdmin&&!terminal)actions+='<button class="button small danger" id="revoke-pkg">撤销复核包</button>';
 if(isAdmin)actions+='<button class="text-button" id="mapping-pkg">查看资产映射（仅负责人）</button>';
 let note='';
 if(p.status==='adopted')note='<p class="warning ok-note">已采纳：新样本批次 #'+p.result_dataset_id+' 已生成，原数据批次记录未改动。<a href="#/datasets">前往数据接入查看 ↗</a></p>';
 if(p.status==='revoked')note='<p class="warning">已撤销：下载与回传已立即停止，迟到的处理不再生成批次。</p>';
 let verdictForm='';
 if(isVendor&&p.status==='claimed'){
  const rows=p.items.map(i=>'<tr><td>'+esc(i.alias)+'</td><td>'+esc(i.model)+'</td><td>'+fmt(i.km)+'</td><td>'+mark(i.failed)+'</td><td><select data-verdict="'+esc(i.alias)+'"><option value="1"'+(i.failed===1?' selected':'')+'>失效 1</option><option value="0"'+(i.failed===0?' selected':'')+'>在役 0</option></select></td></tr>').join('');
  verdictForm='<form id="verdict-form"><div class="section-title"><h2>回传复核判定</h2><span>按包内别名登记 · 整单校验</span></div><div class="table-wrap"><table><thead><tr><th>包内别名</th><th>型号</th><th>观测里程</th><th>当前登记</th><th>复核判定</th></tr></thead><tbody>'+rows+'</tbody></table></div><button type="submit" class="primary">提交整单判定</button><p class="hint">跨包别名或缺项将整单拒收；网络中断后重试本单不会生成副本。</p></form>';
 }
 return '<section class="panel"><div class="section-title"><h2>'+esc(p.name)+'</h2>'+chip(p.status)+'</div><div class="timeline-dates">'+dates+'</div><p class="hint">来源批次 '+esc(p.dataset_name)+' · 进度 '+p.verdict_count+'/'+p.item_count+' 件已判定 · 冻结指纹 SHA256 '+esc(p.source_checksum.slice(0,18))+'…</p><div class="action-row">'+actions+'</div>'+note+'<div id="mapping-box"></div><div class="section-title"><h2>冻结样本</h2><span>'+p.item_count+' 件'+(isAdmin?' · 含资产映射':' · 仅包内别名')+'</span></div>'+table(itemColumns(isAdmin),itemRows(p.items),'该包暂无样本')+'</section>'+verdictForm;
}
function subsPanel(subs){
 const rows=subs.length?subs.map(s=>'<article class="subm"><div><strong>'+(s.status==='accepted'?'已接收':'已拒收')+'</strong><span>单号 #'+s.id+' · '+date(s.created_at)+' · '+s.verdict_count+' 项判定</span></div>'+(s.reasons&&s.reasons.length?'<ul class="reason-list">'+s.reasons.map(r=>'<li>'+esc(r)+'</li>').join('')+'</ul>':'')+'</article>').join(''):'<p class="empty">尚无回传记录。</p>';
 return '<section class="panel"><div class="section-title"><h2>回传记录</h2><span>'+subs.length+' 单</span></div>'+rows+'</section>';
}
export async function reviewPage(id){
 const role=session.user.role,isVendor=role==='vendor',canCreate=role==='admin'||role==='analyst';
 const list=await reviewPackages.list();
 let selected=null;
 try{selected=id?await reviewPackages.get(id):(list[0]?await reviewPackages.get(list[0].id):null);}
 catch(e){selected=list[0]?await reviewPackages.get(list[0].id).catch(()=>null):null;}
 currentId=selected?selected.id:null;
 const subs=selected?await reviewPackages.submissions(selected.id):[];
 let ds=[],vendors=[];
 if(!isVendor){[ds,vendors]=await Promise.all([datasets.list(),reviewPackages.vendors()]);}
 if(canCreate&&!pick.datasetId&&ds[0])pick.datasetId=ds[0].id;
 return heading('06 / OUTSOURCED REVIEW','外协复核包','失效状态逐件复核在不暴露车队资产号的前提下进行：样本冻结、包内别名、整单回传、负责人采纳后生成新样本批次。','<button class="button" id="refresh-review">刷新 ↻</button>')+'<div class="review-grid"><section>'+(canCreate?createPanel(ds,vendors):'')+listPanel(list,currentId,isVendor)+'</section>'+(selected?'<section>'+detailPanel(selected,role)+subsPanel(subs)+'</section>':'<section class="panel"><p class="empty">请选择左侧复核包查看详情。</p></section>')+'</div>';
}
const filtered=()=>pick.records.filter(r=>!pick.model||String(r.model)===pick.model);
const count=()=>{const el=document.querySelector('#pick-count');if(el)el.textContent='已选 '+pick.assets.size+' 件';};
function renderPicker(){
 const list=document.querySelector('#pick-list');
 if(!list)return;
 const ms=document.querySelector('#pick-model');
 if(ms){const models=[...new Set(pick.records.map(r=>String(r.model)))];ms.innerHTML='<option value="">全部型号</option>'+models.map(m=>'<option value="'+esc(m)+'"'+(pick.model===m?' selected':'')+'>'+esc(m)+'</option>').join('');}
 list.innerHTML=filtered().map(r=>{const a=String(r.asset);return '<label class="pick-row"><input type="checkbox" data-asset="'+esc(a)+'"'+(pick.assets.has(a)?' checked':'')+'><span>'+esc(a)+' · '+esc(r.model)+' · '+fmt(r.km)+' 公里 · '+mark(r.failed)+'</span></label>';}).join('')||'<p class="hint">该批次没有匹配样本。</p>';
 list.querySelectorAll('[data-asset]').forEach(c=>c.onchange=()=>{if(c.checked)pick.assets.add(c.dataset.asset);else pick.assets.delete(c.dataset.asset);count();});
 count();
}
export function bindReview(refresh){
 document.querySelector('#refresh-review')?.addEventListener('click',refresh);
 document.querySelectorAll('[data-pkg]').forEach(b=>b.onclick=()=>{location.hash='#/review/'+b.dataset.pkg;});
 const form=document.querySelector('#package-form');
 if(form){
  const dsSelect=form.querySelector('#pick-dataset');
  const load=async id=>{try{const d=await datasets.get(id);pick.records=d.records;pick.datasetId=d.id;renderPicker();}catch(e){notify(e.message,true);}};
  dsSelect.onchange=()=>{pick.assets.clear();pick.model='';load(Number(dsSelect.value));};
  form.querySelector('#pick-model').onchange=e=>{pick.model=e.target.value;renderPicker();};
  form.querySelector('#pick-all').onclick=()=>{filtered().forEach(r=>pick.assets.add(String(r.asset)));renderPicker();};
  form.querySelector('#pick-none').onclick=()=>{pick.assets.clear();renderPicker();};
  load(Number(dsSelect.value));
  submit(form,async f=>{
   if(!pick.assets.size)throw new Error('请至少选定一件样本');
   await reviewPackages.create({name:f.get('name'),dataset_id:Number(f.get('dataset_id')),vendor_id:Number(f.get('vendor_id')),assets:[...pick.assets]});
   notify('复核包已冻结并分配，等待外协领取');
   pick.assets.clear();
   await refresh();
  });
 }
 const cid=currentId,on=(sel,fn)=>{const el=document.querySelector(sel);if(el)el.onclick=fn;};
 on('#claim-pkg',async e=>{e.target.disabled=true;try{await reviewPackages.claim(cid);notify('已领取，可下载复核表并开始判定');await refresh();}catch(err){notify(err.message,true);e.target.disabled=false;}});
 on('#download-pkg',()=>{downloadFile(reviewPackages.download(cid),'复核包-'+cid+'.csv').catch(e=>notify(e.message,true));});
 on('#adopt-pkg',async e=>{if(!confirm('采纳后将以外协判定生成新样本批次，原数据批次记录不变。确认采纳？'))return;e.target.disabled=true;try{const p=await reviewPackages.adopt(cid);notify('已采纳，新样本批次 #'+p.result_dataset_id+' 已生成');await refresh();}catch(err){notify(err.message,true);e.target.disabled=false;}});
 on('#revoke-pkg',async e=>{if(!confirm('撤销后立即停止下载与回传，且不可恢复。确认撤销？'))return;e.target.disabled=true;try{await reviewPackages.revoke(cid);notify('复核包已撤销，下载与回传已停止');await refresh();}catch(err){notify(err.message,true);e.target.disabled=false;}});
 on('#mapping-pkg',async e=>{e.target.disabled=true;try{const rows=await reviewPackages.mapping(cid);document.querySelector('#mapping-box').innerHTML='<div class="section-title"><h2>资产映射</h2><span>仅负责人可见 · 已留痕</span></div>'+table(itemColumns(true).slice(1),itemRows(rows));}catch(err){notify(err.message,true);}e.target.disabled=false;});
 const vf=document.querySelector('#verdict-form');
 if(vf)submit(vf,async()=>{
  const verdicts=[...vf.querySelectorAll('[data-verdict]')].map(s=>({alias:s.dataset.verdict,failed:Number(s.value)}));
  const key=submitKeys[cid]||(submitKeys[cid]=uuid());
  const res=await reviewPackages.submit(cid,{verdicts},key);
  delete submitKeys[cid];
  if(res.status==='accepted')notify('回传已接收，等待负责人采纳');
  else notify('整单被拒收：'+(res.reasons[0]||'')+(res.reasons.length>1?' 等 '+res.reasons.length+' 项':''),true);
  await refresh();
 });
}
