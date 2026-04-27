import pytest
from unittest.mock import patch

@pytest.mark.asyncio
async def test_upload_receipt_endpoint(client):
    # Mock the Celery task .delay() method
    with patch("app.api.endpoints.receipts.process_receipt_task.delay") as mock_task:
        mock_task.return_value.id = "fake-task-id"
        
        # Simulate a file upload
        files = {"file": ("test.jpg", b"fake-image-content", "image/jpeg")}
        data = {"chat_id": "12345"}
        
        response = await client.post("/api/v1/receipts/upload", files=files, data=data)
        
        assert response.status_code == 202
        assert response.json()["task_id"] == "fake-task-id"
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_get_export_status_not_found(client):
    fake_task_id = "non-existent-id"
    
    # Mock AsyncResult so it looks like an unknown task
    with patch("app.api.endpoints.exports.AsyncResult") as mock_result:
        mock_result.return_value.state = "PENDING"
        mock_result.return_value.info = None 
        
        response = await client.get(f"/api/v1/exports/export/status/{fake_task_id}")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_export_status_success(client, tmp_path):
    # Create a dummy file to satisfy os.path.exists()
    fake_file = tmp_path / "test.xlsx"
    fake_file.write_text("dummy data")
    
    with patch("app.api.endpoints.exports.AsyncResult") as mock_res:
        mock_res.return_value.state = "SUCCESS"
        mock_res.return_value.result = {"file_path": str(fake_file)}
        
        response = await client.get("/api/v1/exports/export/status/some-id")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

@pytest.mark.asyncio
async def test_get_export_status_failure(client):
    with patch("app.api.endpoints.exports.AsyncResult") as mock_res:
        mock_res.return_value.state = "FAILURE"
        mock_res.return_value.info = "Database connection error"
        
        response = await client.get("/api/v1/exports/export/status/fail-id")
        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"

@pytest.mark.asyncio
async def test_upload_receipt_invalid_type(client):
    files = {"file": ("test.txt", b"hello world", "text/plain")}
    response = await client.post("/api/v1/receipts/upload", files=files)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file type"        

@pytest.mark.asyncio
async def test_get_receipt_status_success(client):
    """Covers app/api/endpoints/receipts.py:46-59"""
    with patch("app.api.endpoints.receipts.AsyncResult") as mock_res:
        mock_res.return_value.status = "SUCCESS"
        mock_res.return_value.result = {"receipt_id": 1, "merchant": "REWE"}
        
        response = await client.get("/api/v1/receipts/upload/status/task-123")
        assert response.status_code == 200
        assert response.json()["result"]["merchant"] == "REWE"

@pytest.mark.asyncio
async def test_get_receipt_status_failure(client):
    with patch("app.api.endpoints.receipts.AsyncResult") as mock_res:
        mock_res.return_value.status = "FAILURE"
        mock_res.return_value.info = "OCR Engine Timeout"
        
        response = await client.get("/api/v1/receipts/upload/status/task-fail")
        assert response.json()["error"] == "OCR Engine Timeout"    