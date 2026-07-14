"""Upload and job API views."""

import logging
import os
import tempfile
from pathlib import Path

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .file_reader import paginate_uploaded_file
from .identifiers import new_upload_id
from .models import Job, UploadedFile
from .result_reader import paginate_parquet_result
from .services import get_file_columns, is_allowed_upload

logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50


def _save_to_storage_with_key(temp_path: str, storage_key: str) -> tuple[str, str]:
    """Stream a temp file into FileSystemStorage; returns (absolute_path, stored_name).

    Uses Django's File wrapper so FileSystemStorage drains the file via
    File.chunks() — the entire file is never loaded into RAM.
    """
    with open(temp_path, "rb") as handle:
        stored_name = default_storage.save(storage_key, File(handle))
    return default_storage.path(stored_name), stored_name


def _finalise_record(record_id: str, filename: str, file_path: str, stored_name: str) -> None:
    record = UploadedFile.objects.get(id=record_id)
    record.original_filename = filename
    record.saved_filename = stored_name
    record.file_path = file_path
    record.save()


def create_initial_record(filename: str) -> UploadedFile:
    """Create a DB row immediately so the client gets an upload id before save finishes."""
    return UploadedFile.objects.create(
        id=new_upload_id(),
        original_filename=filename,
        file_path="",
        saved_filename="",
    )


def _stream_upload_to_temp(uploaded_file, filename: str) -> str:
    """Write the request upload to a temp file while enforcing MAX_UPLOAD_BYTES."""
    suffix = Path(filename).suffix.lower()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    total_bytes = 0
    try:
        for chunk in uploaded_file.chunks():
            total_bytes += len(chunk)
            if total_bytes > settings.MAX_UPLOAD_BYTES:
                raise ValueError(
                    f"Upload exceeds maximum size of {settings.MAX_UPLOAD_BYTES} bytes"
                )
            temp_file.write(chunk)
        temp_file.close()
        return temp_file.name
    except Exception:
        temp_file.close()
        os.remove(temp_file.name)
        raise


@csrf_exempt
async def instant_id_upload_view(request):
    """Stream upload to disk, then dispatch a Celery task for column cache warm-up.

    Memory behaviour: _stream_upload_to_temp writes the file in chunks (never
    fully in RAM); _save_to_storage drains the temp file via File.chunks() so
    FileSystemStorage copies it without buffering the full content.  No full-file
    bytes object is ever constructed.

    Web and worker share the media Docker volume, so the Celery task can read
    the saved file directly without any additional transfer.
    """
    if request.method != "POST" or not request.FILES.get("file"):
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

    uploaded_file = request.FILES["file"]
    filename = uploaded_file.name

    if not is_allowed_upload(filename):
        return JsonResponse(
            {"error": "Unsupported file type. Allowed types: CSV, XLSX"},
            status=400,
        )

    temp_path: str | None = None
    try:
        # 1. Write to a named temp file with size enforcement (chunk-by-chunk).
        temp_path = await sync_to_async(_stream_upload_to_temp)(uploaded_file, filename)

        # 2. Reserve a DB row to get a stable record_id.
        record = await sync_to_async(create_initial_record)(filename)
        record_id = str(record.id)

        # 3. Stream temp → FileSystemStorage using File.chunks() (no RAM spike).
        #    stored_name is relative (e.g. uploads/<id>/file.csv);
        #    file_path is the absolute path on the shared media volume.
        storage_key = f"uploads/{record_id}/{filename}"
        file_path, stored_name = await sync_to_async(_save_to_storage_with_key)(
            temp_path, storage_key
        )

        # 4. Persist both paths on the DB row.
        await sync_to_async(_finalise_record)(record_id, filename, file_path, stored_name)

        # 5. Dispatch Celery task to warm the column cache on the worker.
        from uploads.tasks import warm_upload_columns  # avoid circular import
        await sync_to_async(warm_upload_columns.apply_async)((record_id,))

        return JsonResponse(
            {
                "status": "processing",
                "message": "Upload complete.",
                "uploaded_file_id": record_id,
            },
            status=202,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("Upload failed")
        return JsonResponse({"status": "error", "message": "Internal server error"}, status=500)
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Failed to remove temp upload file %s", temp_path)


def _serialize_job(job: Job) -> dict:
    prompt = job.natural_language_prompt
    if len(prompt) > 80:
        prompt = f"{prompt[:77]}..."

    payload = {
        "job_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "transform_type": job.transform_type,
        "created_at": job.created_at.isoformat(),
        "natural_language_prompt": prompt,
        "replacement_value": job.replacement_value,
        "target_columns": job.target_columns,
    }
    if job.find_value:
        payload["find_value"] = job.find_value
    if job.generated_regex:
        payload["generated_regex"] = job.generated_regex
    if job.total_rows is not None:
        payload["total_rows"] = job.total_rows
        payload["rows_processed"] = job.rows_processed
    return payload


def list_uploads_view(request):
    """List uploaded files and any jobs created from them."""
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed"}, status=405)

    records = UploadedFile.objects.prefetch_related("jobs").order_by("-uploaded_at")
    uploads = []

    for record in records:
        jobs = [_serialize_job(job) for job in record.jobs.order_by("-created_at")]
        uploads.append(
            {
                "uploaded_file_id": str(record.id),
                "filename": record.original_filename,
                "status": "ready" if record.file_path else "processing",
                "uploaded_at": record.uploaded_at.isoformat(),
                "jobs": jobs,
            }
        )

    return JsonResponse({"uploads": uploads})


def test(request):
    return HttpResponse("Hello bro")


def uploaded_file_status_view(request, uploaded_file_id):
    """Poll until background storage finishes, then return available columns."""
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed"}, status=405)

    try:
        record = UploadedFile.objects.get(pk=uploaded_file_id)
    except UploadedFile.DoesNotExist:
        return JsonResponse({"error": "Uploaded file not found"}, status=404)

    if not record.file_path:
        return JsonResponse(
            {
                "uploaded_file_id": str(record.id),
                "status": "processing",
                "filename": record.original_filename,
                "message": "Upload still in progress",
            },
            status=202,
        )

    try:
        columns = get_file_columns(record.file_path, str(record.id))
    except FileNotFoundError:
        return JsonResponse(
            {
                "uploaded_file_id": str(record.id),
                "status": "processing",
                "filename": record.original_filename,
                "message": "File not yet available on disk",
            },
            status=202,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        logger.exception("Failed to read columns for upload %s", uploaded_file_id)
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse(
        {
            "uploaded_file_id": str(record.id),
            "status": "ready",
            "filename": record.original_filename,
            "columns": columns,
        }
    )


def uploaded_file_data_view(request, uploaded_file_id):
    """Return a paginated preview of the original uploaded file."""
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed"}, status=405)

    try:
        record = UploadedFile.objects.get(pk=uploaded_file_id)
    except UploadedFile.DoesNotExist:
        return JsonResponse({"error": "Uploaded file not found"}, status=404)

    if not record.file_path:
        return JsonResponse(
            {"uploaded_file_id": str(record.id), "status": "processing"},
            status=202,
        )

    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", DEFAULT_PAGE_SIZE))
    except ValueError:
        return JsonResponse({"error": "page and page_size must be integers"}, status=400)

    if page < 1:
        return JsonResponse({"error": "page must be >= 1"}, status=400)
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        return JsonResponse(
            {"error": f"page_size must be between 1 and {MAX_PAGE_SIZE}"}, status=400
        )

    try:
        page_data = paginate_uploaded_file(
            record.file_path,
            page,
            page_size,
            uploaded_file_id=str(record.id),
        )
    except FileNotFoundError:
        return JsonResponse({"error": "File not yet available"}, status=202)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("Failed to read uploaded file data for %s", uploaded_file_id)
        return JsonResponse({"error": "Failed to read file"}, status=500)

    return JsonResponse(
        {
            "uploaded_file_id": str(record.id),
            "filename": record.original_filename,
            "page": page,
            "page_size": page_size,
            **page_data,
        }
    )


def job_results_view(request, job_id):
    """Return one page of transformed rows from the job's Parquet output."""
    if request.method != "GET":
        return JsonResponse({"error": "Only GET requests are allowed"}, status=405)

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)

    if job.status != Job.Status.SUCCESS:
        return JsonResponse(
            {
                "error": "Results not ready",
                "status": job.status,
            },
            status=409,
        )

    if not job.result_path:
        return JsonResponse({"error": "No result available for this job"}, status=404)

    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", DEFAULT_PAGE_SIZE))
    except ValueError:
        return JsonResponse({"error": "page and page_size must be integers"}, status=400)

    if page < 1:
        return JsonResponse({"error": "page must be >= 1"}, status=400)
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        return JsonResponse(
            {"error": f"page_size must be between 1 and {MAX_PAGE_SIZE}"},
            status=400,
        )

    try:
        page_data = paginate_parquet_result(
            job.result_path,
            page,
            page_size,
            job_id=str(job.id),
        )
    except FileNotFoundError:
        return JsonResponse({"error": "Processed result file not found"}, status=404)
    except Exception as exc:
        logger.exception("Failed to read paginated results for job %s", job_id)
        return JsonResponse({"error": str(exc)}, status=500)

    if page_data["total_rows"] == 0:
        return JsonResponse(
            {
                "job_id": str(job.id),
                "page": page,
                "page_size": page_size,
                "total_rows": 0,
                "total_pages": 0,
                "columns": page_data["columns"],
                "rows": [],
                "message": "Job completed with no rows in the result",
            }
        )

    return JsonResponse(
        {
            "job_id": str(job.id),
            "page": page,
            "page_size": page_size,
            "total_rows": page_data["total_rows"],
            "total_pages": page_data["total_pages"],
            "columns": page_data["columns"],
            "rows": page_data["rows"],
        }
    )
