import {api} from './api/client.js';
import {session} from './stores/session.js';
import {workspace} from './stores/workspace.js';
import {shell} from './components/common/shell.js';
import {route} from './router/index.js';
import {login} from './pages/login.js';
import {overview} from './pages/overview.js';
import {dataPage,bindData} from './pages/datasets.js';
import {workbench,bindWorkbench} from './pages/workbench.js';
import {results,bindResults} from './pages/results.js';
import {reportPage,bindReports} from './pages/reports.js';
import {reviewPage,bindReview} from './pages/review.js';
import {esc} from './utils/dom.js';
async function render(){
 const app=document.querySelector('#app');
 try{
   if(!workspace.meta){workspace.meta=await api('/meta');document.title=workspace.meta.name;document.documentElement.style.setProperty('--accent',workspace.meta.accent||'oklch(48% 0.13 145)');document.body.dataset.style=workspace.meta.style||'ledger';}
   const {page,id}=route();
   if(!session.token||page==='login'){login();return;}
   const p=session.user.role==='vendor'&&page!=='review'?'review':page;
   const pages={overview,datasets:dataPage,workbench,results:()=>results(id),reports:reportPage,review:()=>reviewPage(id)};
   const content=await (pages[p]||overview)();app.innerHTML=shell(p,content);
   document.querySelector('#logout').onclick=()=>{session.clear();location.hash='#/login';render();};
   if(p==='datasets')bindData(render);if(p==='workbench')bindWorkbench();if(p==='results')bindResults(render);if(p==='reports')bindReports(render);if(p==='review')bindReview(render);
 }catch(e){app.innerHTML='<div class="fatal"><h1>暂时无法打开工作室</h1><p>'+esc(e.message)+'</p><button onclick="location.reload()">重新连接</button></div>';}
}
addEventListener('hashchange',render);render();
