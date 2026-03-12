# Coding Rules & Architecture Guide

> VDA5050 Fleet Adapter - 프로젝트 코딩 규칙 및 아키텍처 가이드

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 목적 | VDA5050 표준을 따르는 AGV와 Open-RMF를 연결하는 Fleet Adapter |
| Python | 3.12+ |
| ROS 2 | Jazzy Jalisco (Ubuntu 24.04) |
| 통신 | AGV ↔ Adapter: MQTT / Adapter ↔ RMF: ROS 2 |
| 빌드 | ament_python (colcon) |

---

## 2. 아키텍처: Clean Architecture

### 2.1 레이어 구조

```
vda5050_fleet_adapter/
├── domain/                  # 핵심 비즈니스 로직
│   ├── entities/            # AGV, Order, Action 등 핵심 엔티티
│   ├── value_objects/       # Position, Velocity 등 불변 값 객체
│   ├── events/              # 도메인 이벤트 정의
│   └── exceptions.py        # 도메인 예외 정의
│
├── usecase/                 # 애플리케이션 유스케이스
│   ├── ports/               # 인터페이스 정의 (ABC)
│   │   ├── agv_gateway.py   # AGV 통신 포트
│   │   ├── fleet_gateway.py # RMF Fleet 통신 포트
│   │   └── config_port.py   # 설정 로더 포트
│   ├── process_order.py     # 주문 처리 유스케이스
│   ├── update_agv_state.py  # AGV 상태 업데이트 유스케이스
│   └── handle_action.py     # 즉시 액션 처리 유스케이스
│
├── infra/                   # 외부 시스템 어댑터
│   ├── mqtt/                # MQTT 클라이언트 구현
│   │   ├── mqtt_client.py   # paho-mqtt 래퍼
│   │   └── vda5050_mqtt_adapter.py  # AGV Gateway 구현체
│   ├── ros2/                # ROS 2 어댑터
│   │   ├── fleet_adapter_node.py    # RMF Fleet Adapter 노드
│   │   └── ros2_fleet_gateway.py    # Fleet Gateway 구현체
│   └── config/              # 설정 로더 구현
│       └── yaml_config_loader.py
│
├── presentation/            # 진입점
│   └── main.py              # ROS 2 노드 시작점
│
├── __init__.py
└── config/                  # 기본 설정 파일
    └── default_params.yaml
```

### 2.2 의존성 규칙

```
presentation → infra → usecase → domain
                 ↓
          (외부 라이브러리)
```

**절대 규칙:**
- `domain/`은 어떤 외부 라이브러리도 import하지 않는다 (순수 Python만)
- `usecase/`는 `domain/`만 import한다 (rclpy, paho-mqtt 금지)
- `infra/`는 `usecase/ports/`의 ABC를 구현한다
- `presentation/`에서 의존성 주입(DI)으로 조립한다

### 2.3 Port/Adapter 패턴 예시

```python
# usecase/ports/agv_gateway.py (Port - 추상)
from abc import ABC, abstractmethod
from domain.entities.agv_state import AgvState

class AgvGateway(ABC):
    @abstractmethod
    def send_order(self, agv_id: str, order: Order) -> None: ...

    @abstractmethod
    def get_state(self, agv_id: str) -> AgvState: ...

# infra/mqtt/vda5050_mqtt_adapter.py (Adapter - 구현)
class Vda5050MqttAdapter(AgvGateway):
    def __init__(self, mqtt_client: MqttClient) -> None:
        self._client = mqtt_client

    def send_order(self, agv_id: str, order: Order) -> None:
        topic = f"uagv/v2/{order.manufacturer}/{agv_id}/order"
        self._client.publish(topic, order.to_json(), qos=2)
```

---

## 3. 코딩 스타일

### 3.1 기본 규칙

| 규칙 | 내용 |
|------|------|
| 스타일 가이드 | PEP 8 (flake8 적용) |
| 최대 줄 길이 | 99자 |
| Docstring | Google 스타일, PEP 257 준수 |
| Type Hints | 모든 public 함수/메서드에 필수 |
| Import 순서 | stdlib → third-party → local (isort 적용) |

### 3.2 네이밍 컨벤션

```python
# 클래스: PascalCase
class AgvStateManager:
    pass

# 함수/메서드/변수: snake_case
def process_order(order_id: str) -> None:
    current_state = get_current_state()

# 상수: UPPER_SNAKE_CASE
MAX_RETRY_COUNT = 3
DEFAULT_MQTT_PORT = 1883

# Private: 언더스코어 접두사
class FleetAdapter:
    def __init__(self) -> None:
        self._agv_states: dict[str, AgvState] = {}

    def _validate_order(self, order: Order) -> bool:
        ...

# ROS 2 노드 이름: vda5050_ 접두사
NODE_NAME = "vda5050_fleet_adapter_node"

# MQTT 토픽: VDA5050 스펙 준수
# /interfaceName/version/manufacturer/serialNumber/topic
MQTT_TOPIC_TEMPLATE = "uagv/v2/{manufacturer}/{serial_number}/{topic}"
```

### 3.3 Type Hints

```python
# 기본 타입
def calculate_distance(pos_a: Position, pos_b: Position) -> float: ...

# Optional / Union (Python 3.12+ 문법 사용)
def find_agv(agv_id: str) -> AgvState | None: ...

# 컬렉션
def get_active_orders(fleet_id: str) -> list[Order]: ...
def get_agv_map() -> dict[str, AgvState]: ...

# Callable
from collections.abc import Callable
def register_callback(callback: Callable[[str, AgvState], None]) -> None: ...
```

### 3.4 Docstring (Google Style)

```python
def process_vda5050_order(
    agv_id: str,
    order: Order,
    *,
    timeout_sec: float = 30.0,
) -> OrderResult:
    """VDA5050 주문을 처리하여 AGV에 전송한다.

    주문 유효성 검증 후 MQTT를 통해 해당 AGV에 전달한다.
    주문 전송 실패 시 최대 3회 재시도한다.

    Args:
        agv_id: 대상 AGV의 고유 식별자.
        order: 전송할 VDA5050 주문 객체.
        timeout_sec: 주문 응답 대기 시간(초). 기본값 30초.

    Returns:
        주문 처리 결과를 담은 OrderResult 객체.

    Raises:
        AgvNotFoundError: 해당 AGV ID가 등록되어 있지 않을 때.
        OrderValidationError: 주문 데이터가 VDA5050 스펙에 맞지 않을 때.
    """
```

---

## 4. VDA5050 메시지 모델

### 4.1 도메인 엔티티 (dataclass 사용)

```python
from dataclasses import dataclass, field
from enum import StrEnum

class OperatingMode(StrEnum):
    AUTOMATIC = "AUTOMATIC"
    SEMIAUTOMATIC = "SEMIAUTOMATIC"
    MANUAL = "MANUAL"
    SERVICE = "SERVICE"
    TEACHIN = "TEACHIN"

@dataclass(frozen=True)
class AgvPosition:
    """AGV의 현재 위치 (VDA5050 position 객체)."""
    x: float
    y: float
    theta: float
    map_id: str
    position_initialized: bool = True

@dataclass
class AgvState:
    """VDA5050 AGV 상태 메시지 도메인 모델."""
    serial_number: str
    manufacturer: str
    order_id: str = ""
    operating_mode: OperatingMode = OperatingMode.AUTOMATIC
    agv_position: AgvPosition | None = None
    driving: bool = False
    errors: list[AgvError] = field(default_factory=list)
```

### 4.2 VDA5050 JSON 직렬화

- 도메인 엔티티에 `to_dict()` / `from_dict()` 메서드 정의
- VDA5050 스펙의 camelCase 필드명 변환은 infra 레이어에서 처리
- JSON 스키마 검증은 수신/발신 시 infra 레이어에서 수행

---

## 5. 에러 처리

### 5.1 규칙

```python
# 도메인 예외 정의 (domain/exceptions.py)
class DomainError(Exception):
    """도메인 계층 기본 예외."""

class AgvNotFoundError(DomainError):
    """등록되지 않은 AGV 접근 시."""

class OrderValidationError(DomainError):
    """VDA5050 주문 유효성 검증 실패 시."""

class InvalidStateTransitionError(DomainError):
    """허용되지 않는 AGV 상태 전이 시."""
```

### 5.2 로깅 규칙

| 레벨 | 용도 | 예시 |
|------|------|------|
| DEBUG | 프로토콜 상세, 메시지 페이로드 | MQTT 메시지 수신 내용 |
| INFO | 상태 변경, 주요 이벤트 | AGV 연결, 주문 수신/완료 |
| WARN | 복구 가능한 문제 | 재시도, 타임아웃 경고 |
| ERROR | 복구 불가 실패 | MQTT 연결 끊김, 스키마 검증 실패 |

```python
# ROS 2 노드 내부
self.get_logger().info(f"AGV [{agv_id}] connected, state: {state.operating_mode}")

# 비-ROS 컴포넌트
import logging
logger = logging.getLogger(__name__)
logger.debug(f"MQTT message received on topic: {topic}")
```

### 5.3 금지 사항

```python
# 절대 금지: bare except
try:
    ...
except:  # <- 금지
    pass

# 올바른 방법
try:
    ...
except (ConnectionError, TimeoutError) as e:
    logger.error(f"MQTT connection failed: {e}")
    raise
```

---

## 6. MQTT 규칙

| 항목 | 규칙 |
|------|------|
| QoS | State/Visualization: QoS 1, Order/InstantAction: QoS 2 |
| Topic 구조 | `uagv/v2.0.0/{manufacturer}/{serialNumber}/{topic}` |
| Retained | State 메시지: retained=True |
| Reconnect | 자동 재연결, 지수 백오프 (max 60초) |
| Thread Safety | MQTT 콜백과 ROS 2 콜백 간 공유 상태는 `threading.Lock` 사용 |

---

## 7. 설정 관리

- 모든 설정값은 YAML 파라미터로 로딩 (하드코딩 금지)
- ROS 2 `declare_parameter`로 선언 후 사용
- 기본값은 `config/default_params.yaml`에 정의

```yaml
# config/default_params.yaml
vda5050_fleet_adapter:
  ros__parameters:
    fleet_name: "vda5050_fleet"
    mqtt:
      broker_host: "localhost"
      broker_port: 1883
      keepalive_sec: 60
      reconnect_max_delay_sec: 60
    vda5050:
      interface_name: "uagv"
      protocol_version: "v2"
      manufacturer: "default_manufacturer"
    adapter:
      state_publish_rate_hz: 1.0
      order_timeout_sec: 30.0
      max_retry_count: 3
```

---

## 8. 테스트

### 8.1 테스트 구조

```
test/
├── unit/                    # 단위 테스트 (외부 의존성 없음)
│   ├── domain/
│   ├── usecase/
│   └── infra/
├── integration/             # 통합 테스트 (MQTT broker, ROS 2 필요)
├── conftest.py              # 공통 fixture
├── test_flake8.py           # Lint 검사
├── test_copyright.py        # 저작권 검사
└── test_pep257.py           # Docstring 검사
```

### 8.2 테스트 규칙

- **단위 테스트**: ROS 2 런타임, MQTT 브로커에 의존하지 않는다
- **Mock**: Port 경계에서 mock 처리 (usecase의 Port ABC를 mock)
- **파일 명명**: `test_<모듈명>.py`
- **함수 명명**: `test_<대상>_<조건>_<기대결과>`

```python
# test/unit/usecase/test_process_order.py
def test_process_order_valid_order_returns_success():
    ...

def test_process_order_invalid_agv_id_raises_not_found():
    ...
```

### 8.3 실행 명령

```bash
# 전체 테스트
cd ~/rmf_ws && colcon test --packages-select vda5050_fleet_adapter

# 단위 테스트만
cd ~/rmf_ws/src/vda5050_fleet_adapter && python -m pytest test/unit/ -v

# 커버리지
python -m pytest test/unit/ --cov=vda5050_fleet_adapter --cov-report=term-missing
```

---

## 9. Git 커밋 규칙

### 9.1 Conventional Commits

```
<type>(<scope>): <subject>

<body>

<footer>
```

| Type | 용도 |
|------|------|
| feat | 새 기능 |
| fix | 버그 수정 |
| refactor | 리팩토링 (기능 변경 없음) |
| test | 테스트 추가/수정 |
| docs | 문서 수정 |
| chore | 빌드, 설정 변경 |

### 9.2 예시

```
feat(mqtt): add VDA5050 order message publishing

Implement MQTT adapter for sending order messages to AGVs
following VDA5050 v2.0 specification with QoS 2.
```

---

## 10. 의존성 관리

- `package.xml`에 ROS 2 의존성 선언
- `setup.py`의 `install_requires`에 Python 패키지 선언
- 새 의존성 추가 시 반드시 `package.xml`과 `setup.py` 모두 업데이트
- 외부 패키지는 최소한으로 유지