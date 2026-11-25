# =============================================================================
# (c) 2026 Caldera Technologies Ltd.
# Proprietary and confidential.
# Unauthorized copying or distribution is prohibited.
# =============================================================================
#
# CHANGELOG:
# 2026-11-20  (1.13.0, pending)  Fidelity register fix: reorder_files sends
#   PATCH, the only method /api/v1/storage/media/files/reorder takes.
# =============================================================================

"""Contract tests for storage.reorder_files (method, path and body)."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from platformxe import AsyncPlatformXeClient, PlatformXeClient


def _ok(data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.headers = {"content-type": "application/json"}
    body = {"success": True, "data": data}
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.reason_phrase = "OK"
    return resp


def test_reorder_files_sends_patch_with_file_ids():
    client = PlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"reordered": True})) as req:
        result = client.storage.reorder_files(["f1", "f2"])
    args, kwargs = req.call_args
    assert args == ("PATCH", "/api/v1/storage/media/files/reorder")
    assert kwargs["json"] == {"fileIds": ["f1", "f2"]}
    assert result == {"reordered": True}
    client.close()


@pytest.mark.asyncio
async def test_async_reorder_files_sends_patch_with_file_ids():
    client = AsyncPlatformXeClient(api_key="test")
    with patch.object(client._client, "request", return_value=_ok({"reordered": True})) as req:
        result = await client.storage.reorder_files(["f1", "f2"])
    args, kwargs = req.call_args
    assert args == ("PATCH", "/api/v1/storage/media/files/reorder")
    assert kwargs["json"] == {"fileIds": ["f1", "f2"]}
    assert result == {"reordered": True}
    await client.close()
