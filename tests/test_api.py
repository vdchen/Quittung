import pytest
from unittest.mock import patch
from tests.utils import get_url
from app.core.config import settings

AUTH_HEADERS = {"X-API-Key": settings.API_KEY}


@pytest.mark.asyncio
async def test_upload_receipt_endpoint(client):
    with patch("app.api.endpoints.v1.receipts.process_receipt_task.delay") as mock_task:
        mock_task.return_value.id = "fake-task-id"
        files = {"file": ("test.jpg", b"fake-image-content", "image/jpeg")}
        data = {"chat_id": "12345"}
        
        # CORRECT: Call the function with the relative path
        response = await client.post(
            get_url("/receipts/upload"), 
            files=files, 
            data=data,
            headers=AUTH_HEADERS
        )
        
        assert response.status_code == 202
        assert response.json()["task_id"] == "fake-task-id"
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_get_export_status_not_found(client):
    fake_task_id = "non-existent-id"
    with patch("app.api.endpoints.v1.exports.AsyncResult") as mock_result:
        mock_result.return_value.state = "PENDING"
        mock_result.return_value.info = None 
        
        # CORRECT: get_url handles the versioning and slashes
        response = await client.get(
            get_url(f"/exports/status/{fake_task_id}"),
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_export_status_success(client, tmp_path):
    fake_file = tmp_path / "test.xlsx"
    fake_file.write_text("dummy data")
    
    with patch("app.api.endpoints.v1.exports.AsyncResult") as mock_res:
        mock_res.return_value.state = "SUCCESS"
        mock_res.return_value.result = {"file_path": str(fake_file)}
        
        response = await client.get(
            get_url("/exports/status/some-id"),
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

@pytest.mark.asyncio
async def test_get_export_status_failure(client):
    with patch("app.api.endpoints.v1.exports.AsyncResult") as mock_res:
        mock_res.return_value.state = "FAILURE"
        mock_res.return_value.info = "Database connection error"
        
        response = await client.get(
            get_url("/exports/status/fail-id"),
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"

@pytest.mark.asyncio
async def test_upload_receipt_invalid_type(client):
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = await client.post(
        get_url("/receipts/upload"), 
        files=files,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file type"        

@pytest.mark.asyncio
async def test_get_receipt_status_success(client):
    with patch("app.api.endpoints.v1.receipts.AsyncResult") as mock_res:
        mock_res.return_value.status = "SUCCESS"
        mock_res.return_value.result = {"receipt_id": 1, "merchant": "REWE"}
        
        response = await client.get(
            get_url("/receipts/upload/status/task-123"),
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        assert response.json()["result"]["merchant"] == "REWE"

@pytest.mark.asyncio
async def test_get_receipt_status_failure(client):
    with patch("app.api.endpoints.v1.receipts.AsyncResult") as mock_res:
        mock_res.return_value.status = "FAILURE"
        mock_res.return_value.info = "OCR Engine Timeout"
        
        response = await client.get(
            get_url("/receipts/upload/status/task-fail"),
            headers=AUTH_HEADERS
        )
        assert response.json().get("error") == "OCR Engine Timeout"


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    """Verify that requests without a valid API Key are rejected."""
    response = await client.get(get_url("/receipts/upload/status/any-task"))
    assert response.status_code == 403
    assert response.json()["detail"] == "Could not validate API Key"


@pytest.mark.asyncio
async def test_upload_receipt_too_large(client):
    """Verify that files exceeding MAX_UPLOAD_SIZE_MB are rejected with 413."""
    from app.core.config import settings

    # Create fake content that is 1 byte over the limit
    oversized_bytes = b"X" * (settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
    files = {"file": ("big.pdf", oversized_bytes, "application/pdf")}

    response = await client.post(
        get_url("/receipts/upload"),
        files=files,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()