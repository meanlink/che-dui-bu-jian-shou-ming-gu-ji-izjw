import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def package_dict(p, vendor_name=None, item_count=0, verdict_count=0):
    return {'id':p.id, 'name':p.name, 'status':p.status, 'dataset_id':p.dataset_id, 'dataset_name':p.dataset_name,
            'vendor_id':p.vendor_id, 'vendor':vendor_name, 'created_at':p.created_at, 'claimed_at':p.claimed_at,
            'submitted_at':p.submitted_at, 'closed_at':p.closed_at, 'source_checksum':p.source_checksum,
            'accepted_submission_id':p.accepted_submission_id, 'result_dataset_id':p.result_dataset_id,
            'item_count':item_count, 'verdict_count':verdict_count}
def item_public(i):
    return {'seq':i.seq, 'alias':i.alias, 'model':i.model, 'km':i.km, 'failed':i.failed, 'verdict':i.verdict}
def item_mapped(i):
    return {**item_public(i), 'asset':i.asset}
def submission_dict(s):
    return {'id':s.id, 'package_id':s.package_id, 'status':s.status, 'reasons':s.reasons,
            'idempotency_key':s.idempotency_key, 'verdict_count':len(s.payload.get('verdicts',[])), 'created_at':s.created_at}
