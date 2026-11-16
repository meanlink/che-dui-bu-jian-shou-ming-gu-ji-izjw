/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{id:number,name:string,status:string,vendor:string,item_count:number,verdict_count:number,result_dataset_id:?number}} ReviewPackage */
/** @typedef {{id:number,package_id:number,status:string,reasons:string[],verdict_count:number,created_at:number}} ReviewSubmission */
export {};
