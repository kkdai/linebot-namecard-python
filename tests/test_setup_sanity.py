from app import config


def test_project_id_is_test_value():
    assert config.PROJECT_ID == "test-project"
