from enum import Enum
class Role(str, Enum):
    admin = 'admin'
    analyst = 'analyst'
    viewer = 'viewer'
    vendor = 'vendor'
class JobStatus(str, Enum):
    queued = 'queued'
    running = 'running'
    completed = 'completed'
    failed = 'failed'
class PackageStatus(str, Enum):
    assigned = 'assigned'
    claimed = 'claimed'
    submitted = 'submitted'
    adopted = 'adopted'
    revoked = 'revoked'
TERMINAL_STATES = (PackageStatus.adopted.value, PackageStatus.revoked.value)
