import os
import time
from unittest.mock import patch
from app.tasks.worker import cleanup_uploads_task
from app.core.config import settings

def test_cleanup_uploads_task(tmp_path):
    """
    Verify that cleanup_uploads_task deletes files older than the cutoff
    and keeps newer files.
    """
    # Create a dummy uploads directory
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    
    # File 1: Very old (should be deleted)
    old_file = upload_dir / "old_receipt.jpg"
    old_file.write_text("old content")
    
    # File 2: New (should be kept)
    new_file = upload_dir / "new_receipt.jpg"
    new_file.write_text("new content")
    
    # Manually set the mtime of the old file to 48 hours ago
    # settings.UPLOAD_CLEANUP_HOURS defaults to 24
    past_time = time.time() - (settings.UPLOAD_CLEANUP_HOURS + 1) * 3600
    os.utime(str(old_file), (past_time, past_time))
    
    # Patch the directory in the task
    original_getmtime = os.path.getmtime
    
    # We need to make the task look at our tmp_path instead of the real 'uploads'
    # Since 'uploads' is hardcoded in the task, we patch os.listdir and os.path
    with patch("os.listdir", return_value=os.listdir(str(upload_dir))), \
         patch("os.path.isfile", return_value=True), \
         patch("os.path.getmtime", side_effect=lambda p: original_getmtime(os.path.join(str(upload_dir), os.path.basename(p)))), \
         patch("os.remove") as mock_remove:
            
            result = cleanup_uploads_task()
            
            assert result["status"] == "success"
            # It should have called remove on the old file
            # In the real task it would be os.path.join("uploads", filename)
            # So we check if mock_remove was called with the old filename
            mock_remove.assert_called_once()
            args, _ = mock_remove.call_args
            assert "old_receipt.jpg" in args[0]
