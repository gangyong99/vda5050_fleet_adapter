# fleet adater 테스트 방법
 - 모든 테스트 프로그램을 실행 전 "source ~/rmf_ws/install/setup.bash" 를 실행한다. 

## 테스트 실행 프로그램 순서
 1. rmf_core : "ros2 launch rmf_demos vda_office.launch.xml"
 2. vda5050_fleet_manager : "ros2 launch vda5050_fleet_adapter fleet_adapter.launch.xml"
 3. vda5050_robot_simulator : "cd ~/rmf_ws/src/vda5050_robot_simulator && source ~/rmf_ws/src/vda5050_robot_simulator/.venv/bin/activate && python3 run.py" 
 4. task 명령 입력 : "ros2 run rmf_demos_tasks dispatch_patrol -p patrol_D2 patrol_A2 -n 10", "ros2 run rmf_demos_tasks dispatch_patrol -p patrol_B patrol_A2 -n 10"

 ## 테스트 검증 방법
 - ros core에서 발생한 경로 대로 로봇이 이동하는지 확인 한다.
