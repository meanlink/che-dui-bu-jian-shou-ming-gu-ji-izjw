import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const reviewPackages={
 list:()=>api('/review-packages'),
 vendors:()=>api('/review-packages/vendors'),
 get:id=>api('/review-packages/'+id),
 create:data=>api('/review-packages',{method:'POST',body:JSON.stringify(data)}),
 claim:id=>api('/review-packages/'+id+'/claim',{method:'POST'}),
 mapping:id=>api('/review-packages/'+id+'/mapping'),
 download:id=>'/review-packages/'+id+'/download',
 submissions:id=>api('/review-packages/'+id+'/submissions'),
 submit:(id,data,key)=>api('/review-packages/'+id+'/submissions',{method:'POST',body:JSON.stringify(data),headers:{'Idempotency-Key':key}}),
 adopt:id=>api('/review-packages/'+id+'/adopt',{method:'POST'}),
 revoke:id=>api('/review-packages/'+id+'/revoke',{method:'POST'}),
};
