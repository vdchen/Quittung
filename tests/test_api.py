import pytest
from unittest.mock import patch
from tests.utils import get_url


@pytest.mark.asyncio
async def test_upload_receipt_endpoint(client):
    with patch("app.api.endpoints.receipts.process_receipt_task.delay") as mock_task:
        mock_task.return_value.id = "fake-task-id"
        files = {"file": ("test.jpg", b"fake-image-content", "image/jpeg")}
        data = {"chat_id": "12345"}
        
        # CORRECT: Call the function with the relative path
        response = await client.post(get_url("/receipts/upload"), files=files, data=data)
        
        assert response.status_code == 202
        assert response.json()["task_id"] == "fake-task-id"
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_get_export_status_not_found(client):
    fake_task_id = "non-existent-id"
    with patch("app.api.endpoints.exports.AsyncResult") as mock_result:
        mock_result.return_value.state = "PENDING"
        mock_result.return_value.info = None 
        
        # CORRECT: get_url handles the versioning and slashes
        response = await client.get(get_url(f"/exports/export/status/{fake_task_id}"))
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_export_status_success(client, tmp_path):
    fake_file = tmp_path / "test.xlsx"
    fake_file.write_text("dummy data")
    
    with patch("app.api.endpoints.exports.AsyncResult") as mock_res:
        mock_res.return_value.state = "SUCCESS"
        mock_res.return_value.result = {"file_path": str(fake_file)}
        
        response = await client.get(get_url("/exports/export/status/some-id"))
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

@pytest.mark.asyncio
async def test_get_export_status_failure(client):
    with patch("app.api.endpoints.exports.AsyncResult") as mock_res:
        mock_res.return_value.state = "FAILURE"
        mock_res.return_value.info = "Database connection error"
        
        response = await client.get(get_url("/exports/export/status/fail-id"))
        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"

@pytest.mark.asyncio
async def test_upload_receipt_invalid_type(client):
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = await client.post(get_url("/receipts/upload"), files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file type"        

@pytest.mark.asyncio
async def test_get_receipt_status_success(client):
    with patch("app.api.endpoints.receipts.AsyncResult") as mock_res:
        mock_res.return_value.status = "SUCCESS"
        mock_res.return_value.result = {"receipt_id": 1, "merchant": "REWE"}
        
        response = await client.get(get_url("/receipts/upload/status/task-123"))
        assert response.status_code == 200
        assert response.json()["result"]["merchant"] == "REWE"

@pytest.mark.asyncio
async def test_get_receipt_status_failure(client):
    with patch("app.api.endpoints.receipts.AsyncResult") as mock_res:
        mock_res.return_value.status = "FAILURE"
        mock_res.return_value.info = "OCR Engine Timeout"
        
        response = await client.get(get_url("/receipts/upload/status/task-fail"))
        assert response.json().get("error") == "OCR Engine Timeout"