"""VDA5050 Fleet Adapter 도메인 예외 정의."""


class DomainError(Exception):
    """도메인 계층 기본 예외."""


class AgvNotFoundError(DomainError):
    """등록되지 않은 AGV 접근 시."""


class OrderValidationError(DomainError):
    """VDA5050 주문 유효성 검증 실패 시."""


class InvalidStateTransitionError(DomainError):
    """허용되지 않는 AGV 상태 전이 시."""


class MqttConnectionError(DomainError):
    """MQTT 브로커 연결 실패 시."""


class ActionExecutionError(DomainError):
    """액션 실행 실패 시."""
