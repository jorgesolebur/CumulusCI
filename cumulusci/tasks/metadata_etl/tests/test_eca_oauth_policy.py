from unittest import mock

import pytest

from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.tasks.metadata_etl import UpdateEcaOauthPolicy
from cumulusci.tasks.salesforce.tests.util import create_task
from cumulusci.utils.xml import metadata_tree

MD = "{%s}" % metadata_tree.METADATA_NAMESPACE

ECA_OAUTH_POLICY_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ExtlClntAppOauthConfigurablePolicies xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Test Policy</label>
</ExtlClntAppOauthConfigurablePolicies>"""


def _create_task_with_mock_sf(options):
    """Create UpdateEcaOauthPolicy task with mocked Salesforce connection."""
    mock_sf = mock.Mock()
    mock_sf.query.return_value = {
        "records": [{"Username": "admin@example.com"}],
    }
    with mock.patch(
        "cumulusci.tasks.metadata_etl.eca_oauth_policy.get_simple_salesforce_connection",
        return_value=mock_sf,
    ):
        return create_task(UpdateEcaOauthPolicy, options)


class TestUpdateEcaOauthPolicy:
    def test_options__require_at_least_one_update_option(self):
        with mock.patch(
            "cumulusci.tasks.metadata_etl.eca_oauth_policy.get_simple_salesforce_connection",
            return_value=mock.Mock(),
        ):
            with pytest.raises(TaskOptionsError) as e:
                create_task(
                    UpdateEcaOauthPolicy,
                    {
                        "api_names": "SelfCallout",
                    },
                )
        assert "At least one update option must be provided" in e.value.args[0]

    def test_options__api_names_suffix_appended(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "My Policy",
            }
        )
        assert "SelfCallout_oauth_defaultPolicy" in task.api_names

    def test_options__api_names_suffix_preserved_when_already_present(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout_oauth_defaultPolicy",
                "label": "My Policy",
            }
        )
        assert "SelfCallout_oauth_defaultPolicy" in task.api_names

    def test_options__api_names_multiple(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout,OtherApp",
                "label": "My Policy",
            }
        )
        assert "SelfCallout_oauth_defaultPolicy" in task.api_names
        assert "OtherApp_oauth_defaultPolicy" in task.api_names

    def test_to_option_name__camel_case_to_snake_case(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Test",
            }
        )
        assert (
            task._to_option_name("commaSeparatedPermissionSet")
            == "comma_separated_permission_set"
        )
        assert (
            task._to_option_name("isClientCredentialsFlowEnabled")
            == "is_client_credentials_flow_enabled"
        )

    def test_to_metadata_field__snake_case_to_camel_case(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Test",
            }
        )
        assert (
            task._to_metadata_field("comma_separated_permission_set")
            == "CommaSeparatedPermissionSet"
        )
        assert (
            task._to_metadata_field("required_session_level") == "RequiredSessionLevel"
        )

    def test_get_username_by_alias__success(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Test",
            }
        )
        username = task._get_username_by_alias("admin")
        assert username == "admin@example.com"
        task.sf.query.assert_called_once()

    def test_get_username_by_alias__user_not_found(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Test",
            }
        )
        task.sf.query.return_value = {"records": []}
        with pytest.raises(TaskOptionsError) as e:
            task._get_username_by_alias("nonexistent")
        assert "User with alias 'nonexistent' not found or inactive" in e.value.args[0]

    def test_get_username_by_alias__escapes_single_quotes(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Test",
            }
        )
        task._get_username_by_alias("o'reilly")
        call_args = task.sf.query.call_args[0][0]
        assert "o''reilly" in call_args

    def test_transform_entity__string_field_new_element(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "My Updated Label",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}label")
        assert len(entry) == 1
        assert entry[0].text == "My Updated Label"

    def test_transform_entity__string_field_existing_element(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Replaced Label",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}label")
        assert len(entry) == 1
        assert entry[0].text == "Replaced Label"

    def test_transform_entity__string_field_append_missing(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "required_session_level": "STANDARD",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}requiredSessionLevel")
        assert len(entry) == 1
        assert entry[0].text == "STANDARD"

    def test_transform_entity__boolean_field_true(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "is_client_credentials_flow_enabled": True,
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}isClientCredentialsFlowEnabled")
        assert len(entry) == 1
        assert entry[0].text == "true"

    def test_transform_entity__boolean_field_false(self):
        # Use string "false" - Python False is falsy and fails options validation
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "is_guest_code_cred_flow_enabled": "false",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}isGuestCodeCredFlowEnabled")
        assert len(entry) == 1
        assert entry[0].text == "false"

    def test_transform_entity__boolean_field_string_values(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "is_token_exchange_flow_enabled": "true",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}isTokenExchangeFlowEnabled")
        assert len(entry) == 1
        assert entry[0].text == "true"

    def test_transform_entity__execute_handler_as_user_alias(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "execute_handler_as_user_alias": "admin",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}executeHandlerAs")
        assert len(entry) == 1
        assert entry[0].text == "admin@example.com"

    def test_transform_entity__client_credentials_flow_user_alias(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "client_credentials_flow_user_alias": "cci",
            }
        )
        task.sf.query.return_value = {
            "records": [{"Username": "cci@example.com"}],
        }
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        entry = result._element.findall(f".//{MD}clientCredentialsFlowUser")
        assert len(entry) == 1
        assert entry[0].text == "cci@example.com"

    def test_transform_entity__multiple_updates(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Multi Policy",
                "refresh_token_policy_type": "SpecificLifetime",
                "is_client_credentials_flow_enabled": True,
                "execute_handler_as_user_alias": "admin",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        label_elem = result._element.findall(f".//{MD}label")
        assert len(label_elem) == 1
        assert label_elem[0].text == "Multi Policy"

        refresh_elem = result._element.findall(f".//{MD}refreshTokenPolicyType")
        assert len(refresh_elem) == 1
        assert refresh_elem[0].text == "SpecificLifetime"

        bool_elem = result._element.findall(f".//{MD}isClientCredentialsFlowEnabled")
        assert len(bool_elem) == 1
        assert bool_elem[0].text == "true"

        user_elem = result._element.findall(f".//{MD}executeHandlerAs")
        assert len(user_elem) == 1
        assert user_elem[0].text == "admin@example.com"

    def test_transform_entity__returns_metadata(self):
        task = _create_task_with_mock_sf(
            {
                "api_names": "SelfCallout",
                "label": "Test",
            }
        )
        tree = metadata_tree.fromstring(ECA_OAUTH_POLICY_XML)

        result = task._transform_entity(tree, "SelfCallout_oauth_defaultPolicy")

        assert result is tree
