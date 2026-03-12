"""VDA5050 공통 메시지 헤더."""

from dataclasses import dataclass, field
from datetime import datetime, UTC


@dataclass
class Header:
    """모든 VDA5050 메시지의 공통 헤더.

    Args:
        version: 프로토콜 버전 (e.g. '2.0.0').
        manufacturer: AGV 제조사명.
        serial_number: AGV 고유 식별자.
        header_id: 토픽별 증가 카운터.
        timestamp: UTC 타임스탬프 (ISO 8601).
    """

    version: str
    manufacturer: str
    serial_number: str
    header_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
