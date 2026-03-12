# T자 교차로 시나리오 — RMF Planned Path 분석

## 1. 그래프 구조

```
        [A] ----e0----> [B] ----e2----> [C]
        (0,0)   <--e1-- (5,0)  <--e3-- (10,0)
                         |
                        e4 (down)
                         |
                        [D]
                       (5,5)
                         |
                        e5 (up)
                         |
                        [B]
```

- Node: A, B, C, D
- Edge: e0(A→B), e1(B→A), e2(B→C), e3(C→B), e4(B→D), e5(D→B)

---

## 2. 시나리오: Robot1(A→C), Robot2(C→A) 교차

```
  Robot1 -->                   <-- Robot2
   [A] ========= [B] ========= [C]
                   |
                  [D]   (회피 공간)
```

### 2-1. Negotiation 발생 전 (정상 경로)

```
  Robot1: A ──> B ──> C        (최단경로)
  Robot2: C ──> B ──> A        (최단경로)
```

### 2-2. Negotiation 발생 — Robot1이 D로 회피

```
  Step 1: Robot1에 startPause
  Step 2: RMF가 Robot1 경로 재계산
  Step 3: Robot1에 cancelOrder → 새 order

  Robot1 새 경로:
    A ──> B ──> D ──> B ──> C
          |         ^
          v         |
         [D] ──────┘
         (대기 후 복귀)

  Robot2 경로 (변경없음):
    C ──> B ──> A
```

---

## 3. RMF Core publisher 코드 분석 (EasyFullControl.cpp)

### follow_new_path() 흐름:

```
  EasyFullControl.cpp::follow_new_path(cmd_waypoints)
    │
    ├─ 1) planned_path 토픽 publish (line 1118-1158)
    │     waypoints 전체를 순회하며 wp_names 생성
    │     중복 제거: prev_idx == idx → skip
    │
    ├─ 2) CommandExecution queue 생성 (line 1294-1448)
    │     segment별로 Destination 생성
    │     각 segment마다 navigate() 콜백 연결
    │
    └─ 3) queue 순차 실행
          segment 1 → navigate(dest=B) 호출
          segment 2 → navigate(dest=D) 호출
          segment 3 → navigate(dest=B) 호출
          segment 4 → navigate(dest=C) 호출
```

### planned_path publisher 코드 (line 1129-1146):

```cpp
nlohmann::json wp_names = nlohmann::json::array();
std::optional<std::size_t> prev_idx;
for (const auto& wp : waypoints)        // ← 전체 waypoints
{
    if (!wp.graph_index().has_value())   // graph index 없으면 skip
        continue;
    const std::size_t idx = *wp.graph_index();
    if (prev_idx.has_value() && *prev_idx == idx)  // 중복 skip
        continue;
    prev_idx = idx;
    const std::string name = get_vertex_name(graph, wp.graph_index());
    if (!name.empty())
        wp_names.push_back(name);
}
```

### T자 시나리오에서 waypoints → wp_names 변환:

```
  RMF planner output: A → B → D → D(대기) → B → C

  | waypoint  | graph_idx | prev_idx | 동작        |
  |-----------|-----------|----------|-------------|
  | wp_A      | A         | -        | push "A"    |
  | wp_B      | B         | A        | push "B"    |
  | wp_D      | D         | B        | push "D"    |
  | wp_D(대기) | D         | D        | skip (중복) |
  | wp_B      | B         | D        | push "B"    |
  | wp_C      | C         | B        | push "C"    |

  결과: planned_path = ["A", "B", "D", "B", "C"]   ← 전체 경로!
```

### published 메시지:

```json
{
  "robot_name": "Robot1",
  "task_id": "...",
  "plan_id": 123,
  "map": "L1",
  "path": ["A", "B", "D", "B", "C"]
}
```

---

## 4. 코드 트레이싱: navigate() 첫 호출 시

```
  입력:
    destination.name  = "B"   (첫 segment destination)
    destination.final_name = "C"
    planned_path = ["A", "B", "D", "B", "C"]   ← 전체 경로

  ── robot_adapter.py navigate() 트레이싱 ──

  Step 1: RMF planned path 확보
    target = "C" (final_destination)
    rmf_path = ["A", "B", "D", "B", "C"]
    start_node "A" in rmf_path → True
    path = ["A", "B", "D", "B", "C"]

  Step 2: 3-tier 경로 구성
    rmf_path_end = 4                    (len=5, 확장 전 마지막 index)
    target "C" in path → True           → 확장 불필요!

    goal_node = "B"
    base_end_index = path.index("B") = 1  (첫 번째 "B")

    tier1 = path[0:2] = ["A", "B"]              ← Base
    tier2 = path[2:5] = ["D", "B", "C"]         ← Horizon-RMF
    tier3 = path[5:] = []                        ← 확장 없음

  VDA5050 order:
    A(base) → B(base) → D(horizon) → B(horizon) → C(horizon)
```

---

## 5. 정리

```
  planned_path는 전체 경로 ["A", "B", "D", "B", "C"] 를 포함한다.
  (EasyFullControl.cpp::follow_new_path에서 waypoints 전체를 publish)

  따라서:
  - tier3 확장(compute_path)이 필요 없다 (C가 이미 planned_path에 포함)
  - tier2에 회피경로 ["D", "B", "C"]가 정확히 들어간다
  - 전체 order = A(base) → B(base) → D(horizon) → B(horizon) → C(horizon)
```
