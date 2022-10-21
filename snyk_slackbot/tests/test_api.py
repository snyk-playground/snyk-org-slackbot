from unittest.mock import MagicMock, Mock, patch

import pytest

from .. import api
from ..settings import Settings


@pytest.fixture
def valid_settings():
    settings_dict = {
        "slack_bot_token_env_var_name": "SLACK_BOT_TOKEN",
        "slack_app_token_env_var_name": "SLACK_APP_TOKEN",
        "snyk_token_env_var_name": "SNYK_TOKEN",
        "snyk_group_id": "117013c8-62b2-4faf-9031-08552ec2e9c1",
        "allow_duplicate_org_names": False,
        "business_unit_regex_pattern": ".*",
        "team_name_regex_pattern": ".*",
        "command_create_org": "createorg",
        "sso_sign_in_link": "http://google.com",
        "sso_provider_name": "Okta",
    }
    return Settings(settings_dict)


@pytest.fixture
def api_facade(valid_settings):
    return api.SnykApiFacade(valid_settings)


@patch("snyk.models.Organization")
def test_get_org_admins_calls_filter(org_mock):
    api.get_org_admins(org_mock)
    org_mock.members.filter.assert_called_with(role="admin")


def test_org_org_admins_invalid_input_raises_exception():
    with pytest.raises(Exception) as e_info:
        api.get_org_admins(None)
