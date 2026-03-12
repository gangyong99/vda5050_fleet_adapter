"""YamlConfigLoader 유닛 테스트."""

import pytest  # noqa: F401
from vda5050_fleet_adapter.infra.config.yaml_config_loader import (
    YamlConfigLoader,
)
import yaml


@pytest.fixture
def config_yaml(tmp_path):
    """임시 config.yaml 파일을 생성한다."""
    data = {
        'rmf_fleet': {
            'name': 'test_fleet',
            'limits': {'linear': [0.5, 0.75], 'angular': [0.6, 2.0]},
            'robots': {'AGV-001': {'charger': 'charger_1'}},
            'robot_state_update_frequency': 10.0,
        },
        'fleet_manager': {
            'ip': '192.168.1.100',
            'prefix': 'uagv/v2/TestCo',
            'port': 1884,
            'user': 'admin',
            'password': 'secret',
        },
        'reference_coordinates': {
            'L1': {
                'rmf': [[0, 0], [1, 0], [0, 1], [1, 1]],
                'robot': [[0, 0], [10, 0], [0, 10], [10, 10]],
            }
        },
    }
    path = tmp_path / 'config.yaml'
    with open(path, 'w') as f:
        yaml.dump(data, f)
    return str(path)


class TestYamlConfigLoader:
    """YamlConfigLoader 테스트."""

    def test_load_valid_config(self, config_yaml):
        """유효한 설정 파일을 로드한다."""
        loader = YamlConfigLoader()
        data = loader.load(config_yaml, '/fake/nav.yaml')

        assert 'rmf_fleet' in data
        assert data['rmf_fleet']['name'] == 'test_fleet'
        assert 'fleet_manager' in data
        assert data['fleet_manager']['ip'] == '192.168.1.100'

    def test_load_fleet_manager_section(self, config_yaml):
        """fleet_manager 섹션을 올바르게 로드한다."""
        loader = YamlConfigLoader()
        data = loader.load(config_yaml, '/fake/nav.yaml')

        fm = data['fleet_manager']
        assert fm['port'] == 1884
        assert fm['prefix'] == 'uagv/v2/TestCo'
        assert fm['user'] == 'admin'

    def test_load_reference_coordinates(self, config_yaml):
        """reference_coordinates를 올바르게 로드한다."""
        loader = YamlConfigLoader()
        data = loader.load(config_yaml, '/fake/nav.yaml')

        rc = data['reference_coordinates']['L1']
        assert len(rc['rmf']) == 4
        assert len(rc['robot']) == 4

    def test_load_nonexistent_file(self, tmp_path):
        """존재하지 않는 파일에 대해 빈 dict를 반환한다."""
        loader = YamlConfigLoader()
        data = loader.load(
            str(tmp_path / 'nonexistent.yaml'), '/fake/nav.yaml'
        )
        assert data == {}

    def test_load_invalid_yaml(self, tmp_path):
        """잘못된 YAML에 대해 빈 dict를 반환한다."""
        path = tmp_path / 'bad.yaml'
        with open(path, 'w') as f:
            f.write('just a string')
        loader = YamlConfigLoader()
        data = loader.load(str(path), '/fake/nav.yaml')
        assert data == {}

    def test_load_robots_section(self, config_yaml):
        """Robots 섹션을 올바르게 로드한다."""
        loader = YamlConfigLoader()
        data = loader.load(config_yaml, '/fake/nav.yaml')

        robots = data['rmf_fleet']['robots']
        assert 'AGV-001' in robots
        assert robots['AGV-001']['charger'] == 'charger_1'
