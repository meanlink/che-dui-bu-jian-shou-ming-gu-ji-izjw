from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from src.config.database import get_db, Session
from src.models import ReviewItem, ReviewPackage, ReviewSubmission, User
from src.schemas.review import PackageCreateInput, SubmissionInput
from src.middlewares.auth import current_user, internal_user, can_write, admin_only, vendor_user
from src.services import review
from src.services.audit import record
from src.utils.serialization import package_dict, item_public, item_mapped, submission_dict

router = APIRouter(prefix='/review-packages')


def _counts(db, package_id):
    total = db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.package_id == package_id))
    done = db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.package_id == package_id,
                                                                       ReviewItem.verdict.is_not(None)))
    return total or 0, done or 0


def _view(db, pkg):
    total, done = _counts(db, pkg.id)
    vendor = db.get(User, pkg.vendor_id)
    return package_dict(pkg, vendor_name=vendor.name if vendor else None, item_count=total, verdict_count=done)


def _scoped(db, package_id, user):
    pkg = db.get(ReviewPackage, package_id)
    if not pkg:
        raise HTTPException(404, '复核包不存在')
    if user.role == 'vendor' and pkg.vendor_id != user.id:
        raise HTTPException(403, '外协账号仅可访问分配给自己的复核包')
    return pkg


@router.get('')
def listing(db=Depends(get_db), u=Depends(current_user)):
    query = select(ReviewPackage).order_by(ReviewPackage.id.desc())
    if u.role == 'vendor':
        query = query.where(ReviewPackage.vendor_id == u.id)
    return [_view(db, p) for p in db.scalars(query)]


@router.get('/vendors')
def vendors(db=Depends(get_db), u=Depends(internal_user)):
    return [{'id': v.id, 'name': v.name, 'email': v.email}
            for v in db.scalars(select(User).where(User.role == 'vendor').order_by(User.id))]


@router.post('', status_code=201)
def create(data: PackageCreateInput, db=Depends(get_db), u=Depends(can_write)):
    pkg = review.create(db, data, u)
    record(db, u.email, 'package.create', {'id': pkg.id, 'items': len(data.assets), 'vendor': pkg.vendor_id})
    db.commit()
    return _view(db, pkg)


@router.get('/{package_id}')
def detail(package_id: int, db=Depends(get_db), u=Depends(current_user)):
    pkg = _scoped(db, package_id, u)
    items = db.scalars(select(ReviewItem).where(ReviewItem.package_id == pkg.id).order_by(ReviewItem.seq))
    mapped = u.role == 'admin'
    return {**_view(db, pkg), 'items': [(item_mapped if mapped else item_public)(i) for i in items]}


@router.get('/{package_id}/mapping')
def mapping(package_id: int, db=Depends(get_db), u=Depends(admin_only)):
    pkg = _scoped(db, package_id, u)
    items = db.scalars(select(ReviewItem).where(ReviewItem.package_id == pkg.id).order_by(ReviewItem.seq))
    record(db, u.email, 'package.mapping', {'id': pkg.id})
    db.commit()
    return [item_mapped(i) for i in items]


@router.post('/{package_id}/claim')
def claim(package_id: int, db=Depends(get_db), u=Depends(vendor_user)):
    pkg = _scoped(db, package_id, u)
    review.claim(db, pkg)
    record(db, u.email, 'package.claim', {'id': pkg.id})
    db.commit()
    return _view(db, pkg)


@router.get('/{package_id}/download')
def download(package_id: int, db=Depends(get_db), u=Depends(current_user)):
    pkg = _scoped(db, package_id, u)
    if u.role not in ('admin', 'vendor'):
        raise HTTPException(403, '仅负责人与指定外协可下载复核表')
    data = review.download_csv(db, pkg)
    record(db, u.email, 'package.download', {'id': pkg.id})
    db.commit()
    return Response(content=data, media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="review-package-{pkg.id}.csv"'})


@router.post('/{package_id}/submissions')
def submit(package_id: int, data: SubmissionInput, request: Request, db=Depends(get_db), u=Depends(vendor_user)):
    pkg = _scoped(db, package_id, u)
    sub, key = review.submit(db, pkg, u, data, request.headers.get('Idempotency-Key'))
    record(db, u.email, 'package.submit', {'id': pkg.id, 'submission': sub.id, 'status': sub.status})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        with Session() as retry_db:
            dup = retry_db.scalar(select(ReviewSubmission).where(ReviewSubmission.package_id == pkg.id,
                                                                 ReviewSubmission.idempotency_key == key))
            if dup:
                return submission_dict(dup)
            raise
    return submission_dict(sub)


@router.get('/{package_id}/submissions')
def submissions(package_id: int, db=Depends(get_db), u=Depends(current_user)):
    pkg = _scoped(db, package_id, u)
    rows = db.scalars(select(ReviewSubmission).where(ReviewSubmission.package_id == pkg.id)
                      .order_by(ReviewSubmission.id.desc()))
    return [submission_dict(s) for s in rows]


@router.post('/{package_id}/adopt')
def adopt(package_id: int, db=Depends(get_db), u=Depends(admin_only)):
    pkg = _scoped(db, package_id, u)
    pkg, created = review.adopt(db, pkg)
    record(db, u.email, 'package.adopt', {'id': pkg.id, 'result_dataset_id': pkg.result_dataset_id, 'new_batch': created})
    db.commit()
    return _view(db, pkg)


@router.post('/{package_id}/revoke')
def revoke(package_id: int, db=Depends(get_db), u=Depends(admin_only)):
    pkg = _scoped(db, package_id, u)
    pkg, changed = review.revoke(db, pkg)
    record(db, u.email, 'package.revoke', {'id': pkg.id, 'changed': changed})
    db.commit()
    return _view(db, pkg)
