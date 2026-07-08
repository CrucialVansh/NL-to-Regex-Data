"""UUID helpers compatible with Django's UUIDField."""

import uuid

import uuid_utils


def new_upload_id() -> uuid.UUID:
    # uuid_utils returns its own UUID type; Django expects stdlib uuid.UUID.
    return uuid.UUID(str(uuid_utils.uuid7()))


def new_job_id() -> uuid.UUID:
    return uuid.UUID(str(uuid_utils.uuid4()))
