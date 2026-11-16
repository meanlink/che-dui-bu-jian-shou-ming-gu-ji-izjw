"""外协复核包：冻结样本、包内别名、整单回传、终态采纳/撤销。"""
import csv
import hashlib
import io
import json
import secrets
import time
from fastapi import HTTPException
from sqlalchemy import select, update
from src.constants.enums import TERMINAL_STATES
from src.models import Dataset, ReviewItem, ReviewPackage, ReviewSubmission, User
from src.utils.serialization import checksum

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def _package_code(db):
    for _ in range(20):
        code = ''.join(secrets.choice(ALPHABET) for _ in range(4))
        if not db.scalar(select(ReviewPackage.id).where(ReviewPackage.code == code)):
            return code
    raise HTTPException(500, '无法分配复核包代码，请重试')


def create(db, data, user):
    dataset = db.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    vendor = db.get(User, data.vendor_id)
    if not vendor or vendor.role != 'vendor':
        raise HTTPException(422, '请选择有效的外协账号')
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, '复核包名称去除空格后至少需要两个字符')
    wanted, seen = [], set()
    for raw in data.assets:
        asset = str(raw).strip()
        if asset and asset not in seen:
            seen.add(asset)
            wanted.append(asset)
    if not wanted:
        raise HTTPException(422, '请至少选定一件样本')
    by_asset = {}
    for row in dataset.records:
        asset = str(row.get('asset', ''))
        if asset in seen and asset not in by_asset:
            by_asset[asset] = row
    missing = [a for a in wanted if a not in by_asset]
    if missing:
        raise HTTPException(422, '数据批次中找不到资产号：' + '、'.join(missing[:5]))
    code = _package_code(db)
    frozen = [by_asset[a] for a in wanted]
    pkg = ReviewPackage(name=name, dataset_id=dataset.id, dataset_name=dataset.name, code=code,
                        status='assigned', vendor_id=vendor.id, created_by=user.id,
                        created_at=time.time(), source_checksum=checksum(frozen))
    db.add(pkg)
    db.flush()
    for seq, row in enumerate(frozen, 1):
        db.add(ReviewItem(package_id=pkg.id, seq=seq, alias=f'{code}-{seq:03d}',
                          asset=str(row.get('asset', '')), model=str(row.get('model', '')),
                          km=float(row.get('km')), failed=int(float(row.get('failed')))))
    db.flush()
    return pkg


def claim(db, pkg):
    """领取幂等：重复领取返回当前进度，不产生第二条记录。"""
    if pkg.status == 'assigned':
        db.execute(update(ReviewPackage).where(ReviewPackage.id == pkg.id, ReviewPackage.status == 'assigned')
                   .values(status='claimed', claimed_at=time.time()))
        db.flush()
        db.refresh(pkg)
    if pkg.status != 'claimed':
        raise HTTPException(409, '该复核包已关闭，无法领取')
    return pkg


def _submission_key(pkg_id, data):
    canonical = json.dumps({'package': pkg_id, 'verdicts': sorted((v.alias.strip(), v.failed) for v in data.verdicts)},
                           ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def submit(db, pkg, user, data, idem_key=None):
    """整单校验：跨包别名、缺项、重复或非法判定一律整单拒收并留痕；同键重试返回原单。"""
    key = (idem_key or '').strip()[:80] or _submission_key(pkg.id, data)
    existing = db.scalar(select(ReviewSubmission).where(ReviewSubmission.package_id == pkg.id,
                                                        ReviewSubmission.idempotency_key == key))
    if existing:
        return existing, key
    if pkg.status in TERMINAL_STATES:
        raise HTTPException(409, '该复核包已关闭，回传不再受理')
    if pkg.status == 'submitted':
        raise HTTPException(409, '该复核包已完成回传，等待负责人采纳')
    if pkg.status != 'claimed':
        raise HTTPException(409, '请先领取复核包，再回传判定')
    items = list(db.scalars(select(ReviewItem).where(ReviewItem.package_id == pkg.id)))
    owned = {i.alias: i for i in items}
    reasons, seen = [], set()
    for v in data.verdicts:
        alias = v.alias.strip()
        if alias in seen:
            reasons.append(f'别名 {alias} 在同一单中重复提交')
            continue
        seen.add(alias)
        if alias not in owned:
            reasons.append(f'别名 {alias} 不属于本复核包（跨包或未知别名）')
        if v.failed not in (0, 1):
            reasons.append(f'别名 {alias} 的判定值 {v.failed} 非法，只能登记 0 或 1')
    for alias in sorted(a for a in owned if a not in seen):
        reasons.append(f'缺少别名 {alias} 的判定')
    sub = ReviewSubmission(package_id=pkg.id, vendor_id=user.id, idempotency_key=key,
                           status='rejected' if reasons else 'accepted', reasons=reasons,
                           payload={'verdicts': [{'alias': v.alias.strip(), 'failed': v.failed} for v in data.verdicts]},
                           created_at=time.time())
    db.add(sub)
    db.flush()
    if not reasons:
        # 与撤销并发时只允许一个生效；状态已被改变则整单回滚，迟到的处理不留痕。
        res = db.execute(update(ReviewPackage).where(ReviewPackage.id == pkg.id, ReviewPackage.status == 'claimed')
                         .values(status='submitted', submitted_at=time.time(), accepted_submission_id=sub.id))
        if res.rowcount != 1:
            raise HTTPException(409, '复核包状态已变化，请刷新后重试')
        for v in data.verdicts:
            owned[v.alias.strip()].verdict = v.failed
        db.flush()
        db.refresh(pkg)
    return sub, key


def adopt(db, pkg):
    """采纳幂等：已采纳直接返回原批次；与撤销并发时条件更新只放行一个终态。"""
    if pkg.status == 'adopted':
        return pkg, False
    if pkg.status == 'revoked':
        raise HTTPException(409, '该复核包已撤销，迟到的采纳不再生成批次')
    if pkg.status != 'submitted':
        raise HTTPException(409, '外协尚未完成有效回传，不能采纳')
    res = db.execute(update(ReviewPackage).where(ReviewPackage.id == pkg.id, ReviewPackage.status == 'submitted')
                     .values(status='adopted', closed_at=time.time()))
    if res.rowcount != 1:
        db.flush()
        db.refresh(pkg)
        if pkg.status == 'adopted':
            return pkg, False
        raise HTTPException(409, '采纳与撤销并发冲突，该复核包已进入终态')
    items = list(db.scalars(select(ReviewItem).where(ReviewItem.package_id == pkg.id).order_by(ReviewItem.seq)))
    records = [{'asset': i.asset, 'model': i.model, 'km': i.km, 'failed': i.verdict} for i in items]
    dataset = Dataset(name=f'外协复核批次 · 包#{pkg.id} · {pkg.name}'[:160], source=f'review-package-{pkg.id}',
                      records=records, checksum=checksum(records), created_at=time.time())
    db.add(dataset)
    db.flush()
    pkg.result_dataset_id = dataset.id
    db.flush()
    db.refresh(pkg)
    return pkg, True


def revoke(db, pkg):
    """撤销幂等：已撤销直接返回；条件更新保证与采纳并发时只接受一个终态。"""
    if pkg.status == 'revoked':
        return pkg, False
    if pkg.status == 'adopted':
        raise HTTPException(409, '该复核包已采纳，不能撤销')
    res = db.execute(update(ReviewPackage).where(ReviewPackage.id == pkg.id,
                                                 ReviewPackage.status.not_in(TERMINAL_STATES))
                     .values(status='revoked', closed_at=time.time()))
    if res.rowcount != 1:
        db.flush()
        db.refresh(pkg)
        if pkg.status == 'revoked':
            return pkg, False
        raise HTTPException(409, '撤销与采纳并发冲突，该复核包已进入终态')
    db.flush()
    db.refresh(pkg)
    return pkg, True


def _csv_safe(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


def download_csv(db, pkg):
    """复核表只含包内别名，绝不输出原资产号；进入终态后立即停止下载。"""
    if pkg.status in TERMINAL_STATES:
        raise HTTPException(409, '该复核包已关闭，下载已停止')
    items = list(db.scalars(select(ReviewItem).where(ReviewItem.package_id == pkg.id).order_by(ReviewItem.seq)))
    out = io.StringIO()
    out.write('\ufeff')
    writer = csv.writer(out)
    writer.writerow(['包内别名', '型号', '观测运行里程', '当前失效标记'])
    for i in items:
        writer.writerow([_csv_safe(i.alias), _csv_safe(i.model), i.km, i.failed])
    return out.getvalue().encode('utf-8')
