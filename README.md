# VDA5050 Fleet Adapter

VDA5050 표준을 따르는 AGV와 Open-RMF를 연결하는 Fleet Adapter.
AGV와는 MQTT(VDA5050)로, RMF와는 `rmf_fleet_adapter_python`(`rmf_easy`) API로 통신한다.

| 항목 | 내용 |
|------|------|
| Python | 3.12+ |
| ROS 2 | Jazzy Jalisco (Ubuntu 24.04) |
| 아키텍처 | Clean Architecture (4 레이어) |
| VDA5050 | v2.0 |
| RMF API | `rmf_easy` (FleetConfiguration, RobotCallbacks) |

## 주요 기능

### Order 관리
- **1 Task = 1 Order**: RMF Task 단위로 orderID를 유지, Destination 변경 시 `order_update_id` 증가
- **3-Tier 경로 구성**: Base(즉시 실행) + Horizon(RMF 경로) + Horizon(최종 목적지 확장)
- **경로 보간**: sparse waypoint 사이를 `compute_path()`로 자동 보간
- **브리지 경로**: 로봇 현재 위치가 RMF 경로 시작점과 다를 경우 자동 연결
- **Stitching**: Order update 시 이전 Base 마지막 노드의 sequenceId를 유지하여 끊김 없는 전환

### 도착 감지 (Arrival Detection)
- **거리 기반**: 유클리드 거리가 `arrival_threshold`(기본 0.5m) 이하이면 도착
- **Theta 기반**: Base 노드에서 회전각이 `turn_angle_threshold`(기본 15°) 이상이면 heading까지 `allowed_deviation_theta`(기본 15°) 이내로 맞춘 후 도착 보고
- **Action 완료**: `execute_action`은 VDA5050 action_states에서 FINISHED/FAILED 확인

### Negotiation 처리
- RMF `stop()` → `startPause` instantAction 전송
- RMF 새 경로 `navigate()` → `cancelOrder` → 1초 대기 → 새 orderID로 order 전송

### 충전 관리
- nav_graph의 `is_charger` 속성 또는 `dock` 파라미터로 충전 태스크 자동 감지
- charger 노드 제거 후 pre-charger까지 navigate → `startCharging` nodeAction 부착
- 충전 완료 후 다음 order에 `stopCharging` nodeAction 자동 부착
- 충전 중 SOC가 `recharge_soc`에 도달할 때까지 자동 decommission

### Execute Action as NodeAction
- 활성 order가 있으면 `execute_action`을 instantAction 대신 order update의 nodeAction으로 전송
- `track_action_id`로 action 완료를 추적

### Robot Connection 관리
- VDA5050 connection topic 구독으로 연결 상태 캐싱
- 미연결 로봇은 RMF에 `add_robot`하지 않고, navigate 등 명령 전송 전 pre-flight check

### downloadMap
- 로봇 ONLINE 전환 시 `downloadMap` instantAction 자동 전송
- actionParameters: `mapId`, `mapDownloadUrl`, `mapVersion`
- config `download_map` 섹션이 없으면 비활성화

### Commission 자동 업데이트
- VDA5050 state 기반 RMF commission 자동 갱신:
  - OFFLINE/CONNECTIONBROKEN, FATAL error, E-stop, Manual mode → 전체 decommission
  - SEMIAUTOMATIC → 부분 commission (dispatched=false)
  - AUTOMATIC + 정상 → 전체 commission

## 디렉토리 구조

```
vda5050_fleet_adapter/
│
├── CLAUDE.md                              # Claude Code 프로젝트 규칙
├── CODING_RULES.md                        # 코딩 규칙 & 아키텍처 가이드
├── VDA5050_PROTOCOL.md                    # VDA5050 프로토콜 정의서
├── VDA5050_ACTIONS.md                     # VDA5050 액션 정의서
├── package.xml                            # ROS 2 패키지 매니페스트
├── setup.py
│
├── vda5050_fleet_adapter/                 # 메인 패키지
│   │
│   ├── domain/                            # ① 도메인 (순수 Python, 외부 의존성 없음)
│   │   ├── enums.py                       #    StrEnum 9개 (OperatingMode, ActionStatus 등)
│   │   ├── exceptions.py                  #    도메인 예외
│   │   ├── value_objects/                 #    불변 값 객체 (frozen dataclass)
│   │   │   ├── position.py                #      NodePosition, AgvPosition, Velocity
│   │   │   ├── physical.py                #      BoundingBoxReference, LoadDimensions, Corridor
│   │   │   └── trajectory.py              #      ControlPoint, Trajectory (NURBS)
│   │   └── entities/                      #    도메인 엔티티
│   │       ├── header.py                  #      공통 메시지 헤더
│   │       ├── action.py                  #      Action, ActionState (상태 전이 머신)
│   │       ├── node.py                    #      Node, NodeState
│   │       ├── edge.py                    #      Edge, EdgeState
│   │       ├── order.py                   #      Order (validate, Base/Horizon 분리)
│   │       ├── agv_state.py               #      AgvState (전체 AGV 상태 통합)
│   │       ├── error.py                   #      AgvError, AgvInformation
│   │       ├── battery.py                 #      BatteryState
│   │       ├── safety.py                  #      SafetyState
│   │       ├── load.py                    #      Load
│   │       ├── map_state.py               #      AgvMap
│   │       └── connection.py              #      Connection
│   │
│   ├── usecase/                           # ② 유스케이스
│   │   ├── robot_adapter.py               #    RMF↔VDA5050 브릿지 (navigate, stop, action)
│   │   └── ports/                         #    포트 인터페이스 (ABC)
│   │       ├── robot_api.py               #      RobotAPI (navigate, stop, start_activity 등)
│   │       └── config_port.py             #      ConfigPort + MqttConfig, FleetManagerConfig
│   │
│   ├── infra/                             # ③ 인프라 (외부 의존성 격리)
│   │   ├── mqtt/                          #    MQTT/VDA5050 통신
│   │   │   ├── message_serializer.py      #      JSON ↔ 도메인 (camelCase 변환)
│   │   │   ├── mqtt_client.py             #      paho-mqtt 래퍼 (재연결, Last Will)
│   │   │   └── vda5050_robot_api.py       #      RobotAPI 구현체 (Order/InstantActions 발행)
│   │   ├── nav_graph/                     #    내비게이션 그래프
│   │   │   └── graph_utils.py             #      파싱, 경로 탐색, 좌표 변환, theta 계산
│   │   └── config/
│   │       └── yaml_config_loader.py      #      ConfigPort 구현체
│   │
│   ├── presentation/                      # ④ 프레젠테이션 (진입점)
│   │   └── main.py                        #    Entry point (rmf_easy 패턴)
│   │
│   └── config/
│       └── config.yaml                    #    기본 설정 (mrceki 형식)
│
└── test/                                  # 테스트 (304 tests)
    ├── conftest.py                        #    공통 fixture
    └── unit/
        ├── domain/                        #    도메인 테스트
        ├── usecase/                       #    RobotAdapter 테스트
        └── infra/                         #    RobotAPI, graph_utils, serializer 테스트
```

## 아키텍처

### Clean Architecture 의존성 규칙

```
presentation ──→ infra ──→ usecase ──→ domain
```

| 레이어 | 역할 | 의존성 규칙 |
|--------|------|------------|
| **domain** | 엔티티, 값 객체, 예외 | 순수 Python만 사용. 외부 라이브러리 import 금지 |
| **usecase** | RobotAdapter, 포트(ABC) 정의 | domain만 import. rclpy, paho 금지 |
| **infra** | 포트 구현체 (MQTT, nav_graph, config) | usecase/ports의 ABC를 구현 |
| **presentation** | 진입점, DI 조립 | 모든 구현체를 생성하고 usecase에 주입 |

### Port-Adapter 매핑

| Port (ABC) | Adapter (구현체) | 외부 의존성 |
|------------|-----------------|------------|
| `RobotAPI` | `Vda5050RobotAPI` | paho-mqtt |
| `ConfigPort` | `YamlConfigLoader` | pyyaml |

### 데이터 흐름

```
  ┌─────────┐     MQTT      ┌──────────────────────────────────┐    rmf_easy    ┌─────────┐
  │         │  ◄── state ──  │          Fleet Adapter           │  ── position → │         │
  │         │  ◄── conn ───  │                                  │  ── battery →  │         │
  │   AGV   │               │  ┌────────────────────────────┐  │               │  Open-  │
  │ (VDA5050)│  ── order ──→  │  │  RobotAdapter   (usecase)  │  │  ◄─ navigate │   RMF   │
  │         │  ── action ─→  │  │  Vda5050RobotAPI (infra)    │  │  ◄─ stop     │         │
  │         │               │  │  graph_utils     (infra)    │  │  ◄─ action   │         │
  └─────────┘               │  └────────────────────────────┘  │               └─────────┘
                             └──────────────────────────────────┘
```

### 핵심 컴포넌트

- **RobotAdapter** (`usecase/robot_adapter.py`): RMF의 `RobotCallbacks`(navigate, stop, execute_action)을 받아 VDA5050 AGV에 명령을 전달하는 브릿지. 3-Tier 경로 생성, Order 라이프사이클 관리, 도착 감지(거리+theta), Negotiation 처리, 충전 관리, Commission 자동 업데이트 등 핵심 로직 포함.
- **Vda5050RobotAPI** (`infra/mqtt/vda5050_robot_api.py`): MQTT로 VDA5050 Order/InstantActions를 발행하고, AGV State/Connection을 구독하여 캐시. downloadMap 자동 전송, 연결 상태 관리.
- **graph_utils** (`infra/nav_graph/graph_utils.py`): RMF nav graph 파싱, networkx 최단 경로 탐색, nudged 좌표 변환, VDA5050 Node/Edge 생성, Base 노드 theta 계산.
- **main.py** (`presentation/main.py`): rmf_demos_fleet_adapter + mrceki 패턴의 진입점. FleetConfiguration 로드, Adapter 생성, 로봇별 RobotAdapter 생성, 주기적 상태 업데이트 루프 실행.

## 설치 및 빌드

### 의존성

```bash
# ROS 2 의존성
sudo apt install ros-jazzy-rmf-fleet-adapter-python

# Python 의존성
pip install paho-mqtt pyyaml networkx nudged
```

### 빌드

```bash
cd ~/rmf_ws
colcon build --packages-select vda5050_fleet_adapter
source install/setup.bash
```

## 실행

```bash
ros2 run vda5050_fleet_adapter fleet_adapter \
  -c /path/to/config.yaml \
  -n /path/to/nav_graph.yaml
```

### 시뮬레이션 시간 사용

```bash
ros2 run vda5050_fleet_adapter fleet_adapter \
  -c /path/to/config.yaml \
  -n /path/to/nav_graph.yaml \
  -sim
```

### 설정 파일

설정은 `config.yaml`에 정의한다. Open-RMF의 `FleetConfiguration.from_config_files()`가 읽을 수 있는 mrceki/vda5050_fleet_adapter 형식을 사용한다.

```yaml
# Fleet 설정 (Open-RMF FleetConfiguration 호환)
rmf_fleet:
  name: "vda5050_fleet"
  limits:
    linear: [0.5, 0.75]       # velocity, acceleration
    angular: [0.6, 2.0]
  profile:
    footprint: 0.3
    vicinity: 0.5
  reversible: True
  battery_system:
    voltage: 12.0
    capacity: 24.0
    charging_current: 5.0
  recharge_threshold: 0.40           # 40% 이하 시 자동 충전 task 발생
  recharge_soc: 0.8                  # 충전 중 decommission 해제 SOC
  robots:
    AGV-001:
      charger: "charger_1"
  robot_state_update_frequency: 10.0
  arrival_threshold: 0.5             # meters, 거리 기반 도착 판정
  turn_angle_threshold: 15.0         # degrees, theta 판정 최소 회전각
  allowed_deviation_theta: 15.0      # degrees, theta 허용 오차

# MQTT / VDA5050 설정
fleet_manager:
  ip: "127.0.0.1"
  prefix: "uagv/v2/manufacturer"     # MQTT 토픽 prefix
  port: 1883

# 맵 다운로드 (선택사항)
# download_map:
#   map_id: "L1"
#   map_download_url: "http://example.com/map.tar.gz"
#   map_version: "2.4.1"

# 좌표 변환 (선택사항)
# reference_coordinates:
#   L1:
#     rmf: [[0, 0], [1, 0], [0, 1], [1, 1]]
#     robot: [[0, 0], [1, 0], [0, 1], [1, 1]]
```

### 설정 파라미터 상세

| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `arrival_threshold` | 0.5 | 거리 기반 도착 판정 threshold (m) |
| `turn_angle_threshold` | 15.0 | Base 노드에서 theta 판정을 적용하는 최소 회전각 (°) |
| `allowed_deviation_theta` | 15.0 | theta 도착 판정 허용 오차 (°) |
| `recharge_threshold` | 0.40 | 자동 충전 task 발생 SOC threshold |
| `recharge_soc` | 1.0 | 충전 중 decommission 해제 SOC |
| `robot_state_update_frequency` | 10.0 | 상태 업데이트 주기 (Hz) |

## 테스트

```bash
cd ~/rmf_ws/src/vda5050_fleet_adapter

# 전체 테스트 (304 tests)
python3 -m pytest test/ -v

# 단위 테스트만 (301 tests)
python3 -m pytest test/unit/ -v

# colcon 테스트
cd ~/rmf_ws
colcon build --packages-select vda5050_fleet_adapter
colcon test --packages-select vda5050_fleet_adapter
colcon test-result --verbose
```

## 참조

| 문서/레포 | 설명 |
|-----------|------|
| [rmf_demos_fleet_adapter](https://github.com/open-rmf/rmf_demos/tree/main/rmf_demos_fleet_adapter) | RMF 공식 fleet adapter 예제 (rmf_easy 패턴) |
| [mrceki/vda5050_fleet_adapter](https://github.com/mrceki/vda5050_fleet_adapter) | VDA5050 MQTT fleet adapter 참조 구현 |
| [CODING_RULES.md](CODING_RULES.md) | 코딩 규칙, 네이밍 컨벤션, 아키텍처 상세 |
| [VDA5050_PROTOCOL.md](VDA5050_PROTOCOL.md) | VDA5050 v2.0 통신 프로토콜 전체 정의 |
| [VDA5050_ACTIONS.md](VDA5050_ACTIONS.md) | VDA5050 액션 정의서 (downloadMap, charging 등) |
| [VDA5050 공식 스펙](https://github.com/VDA5050/VDA5050/blob/main/VDA5050_EN.md) | VDA5050 원본 스펙 문서 |
