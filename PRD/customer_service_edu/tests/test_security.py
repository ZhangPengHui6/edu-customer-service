"""身份令牌与消息校验的单元测试。"""

from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from edu_cs.config import get_settings
from edu_cs.schemas.chat import ChatMessageRequest
from edu_cs.security import (
    Principal,
    TokenError,
    create_access_token,
    decode_access_token,
)


def _principal(**overrides) -> Principal:
    payload = {
        "user_id": uuid4(),
        "tenant_id": uuid4(),
        "tenant_code": "dlr_north",
        "tenant_type": "DEALER",
        "role": "customer",
        "name": "家长测试",
    }
    payload.update(overrides)
    return Principal(**payload)


def test_token_roundtrip() -> None:
    principal = _principal()
    decoded = decode_access_token(create_access_token(principal))
    assert decoded == principal


def test_expired_token_rejected() -> None:
    token = create_access_token(_principal(), ttl_seconds=-1)
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_wrong_signature_rejected() -> None:
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "tenant_code": "dlr_north",
            "tenant_type": "DEALER",
            "role": "customer",
            "name": "伪造",
            "iss": "edu-customer-service",
        },
        "another-secret",
        algorithm=get_settings().jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_hq_admin_flag() -> None:
    assert _principal(tenant_type="HQ", role="admin").is_hq_admin
    assert not _principal(tenant_type="HQ", role="agent").is_hq_admin
    assert not _principal(tenant_type="DEALER", role="admin").is_hq_admin


def test_text_message_requires_text() -> None:
    with pytest.raises(ValidationError):
        ChatMessageRequest(message_id=uuid4(), content={"text": "   "})


def test_image_message_requires_http_url() -> None:
    with pytest.raises(ValidationError):
        ChatMessageRequest(
            message_id=uuid4(), type="image", content={"url": "file:///etc/passwd"}
        )
