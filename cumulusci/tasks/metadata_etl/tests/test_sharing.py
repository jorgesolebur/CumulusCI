from datetime import datetime
from unittest import mock

import pytest

from cumulusci.core.exceptions import CumulusCIException, TaskOptionsError
from cumulusci.tasks.metadata_etl import SetOrgWideDefaults
from cumulusci.tasks.salesforce.tests.util import create_task
from cumulusci.utils.xml import metadata_tree

MD = "{%s}" % metadata_tree.METADATA_NAMESPACE

CUSTOMOBJECT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <sharingModel>Read</sharingModel>
    <externalSharingModel>Read</externalSharingModel>
    <label>Test</label>
    <pluralLabel>Tests</pluralLabel>
    <nameField>
        <label>Test Name</label>
        <trackHistory>false</trackHistory>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
</CustomObject>"""

CUSTOMOBJECT_XML_MISSING_TAGS = b"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Test</label>
    <pluralLabel>Tests</pluralLabel>
    <nameField>
        <label>Test Name</label>
        <trackHistory>false</trackHistory>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
</CustomObject>"""

# Metadata where only externalSharingModel is ControlledByParent
CUSTOMOBJECT_XML_EXTERNAL_CBP = b"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <sharingModel>Read</sharingModel>
    <externalSharingModel>ControlledByParent</externalSharingModel>
    <label>Test</label>
    <pluralLabel>Tests</pluralLabel>
    <nameField>
        <label>Test Name</label>
        <trackHistory>false</trackHistory>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
</CustomObject>"""

# Metadata where only sharingModel is ControlledByParent
CUSTOMOBJECT_XML_INTERNAL_CBP = b"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <sharingModel>ControlledByParent</sharingModel>
    <externalSharingModel>Read</externalSharingModel>
    <label>Test</label>
    <pluralLabel>Tests</pluralLabel>
    <nameField>
        <label>Test Name</label>
        <trackHistory>false</trackHistory>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
</CustomObject>"""

# Metadata where both models are ControlledByParent
CUSTOMOBJECT_XML_BOTH_CBP = b"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <sharingModel>ControlledByParent</sharingModel>
    <externalSharingModel>ControlledByParent</externalSharingModel>
    <label>Test</label>
    <pluralLabel>Tests</pluralLabel>
    <nameField>
        <label>Test Name</label>
        <trackHistory>false</trackHistory>
        <type>Text</type>
    </nameField>
    <deploymentStatus>Deployed</deploymentStatus>
</CustomObject>"""


class TestSetOrgWideDefaults:
    def test_sets_owd(self):
        task = create_task(
            SetOrgWideDefaults,
            {
                "managed": True,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": [
                    {
                        "api_name": "Account",
                        "internal_sharing_model": "Private",
                        "external_sharing_model": "Private",
                    },
                    {
                        "api_name": "Test__c",
                        "internal_sharing_model": "ReadWrite",
                        "external_sharing_model": "Read",
                    },
                ],
            },
        )

        assert task.api_names == set(["Account", "Test__c"])

        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML)

        result = task._transform_entity(tree, "Test__c")

        entry = result._element.findall(f".//{MD}sharingModel")
        assert len(entry) == 1
        assert entry[0].text == "ReadWrite"

        entry = result._element.findall(f".//{MD}externalSharingModel")
        assert len(entry) == 1
        assert entry[0].text == "Read"

    def test_sets_owd__missing_tags(self):
        task = create_task(
            SetOrgWideDefaults,
            {
                "managed": True,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": [
                    {
                        "api_name": "Account",
                        "internal_sharing_model": "Private",
                        "external_sharing_model": "Private",
                    },
                    {
                        "api_name": "Test__c",
                        "internal_sharing_model": "ReadWrite",
                        "external_sharing_model": "Read",
                    },
                ],
            },
        )

        assert task.api_names == set(["Account", "Test__c"])

        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML_MISSING_TAGS)

        result = task._transform_entity(tree, "Test__c")._element

        entry = result.findall(f".//{MD}sharingModel")
        assert len(entry) == 1
        assert entry[0].text == "ReadWrite"

        entry = result.findall(f".//{MD}externalSharingModel")
        assert len(entry) == 1
        assert entry[0].text == "Read"

    def test_post_deploy_waits_for_enablement(self):
        task = create_task(
            SetOrgWideDefaults,
            {
                "managed": True,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": [
                    {
                        "api_name": "Account",
                        "internal_sharing_model": "Private",
                        "external_sharing_model": "Private",
                    },
                    {
                        "api_name": "Test__c",
                        "internal_sharing_model": "ReadWrite",
                        "external_sharing_model": "Read",
                    },
                ],
            },
        )
        task.sf = mock.Mock()
        task.sf.query.side_effect = [
            {
                "totalSize": 1,
                "records": [
                    {"ExternalSharingModel": "Read", "InternalSharingModel": "Read"}
                ],
            },
            {
                "totalSize": 1,
                "records": [
                    {
                        "ExternalSharingModel": "Private",
                        "InternalSharingModel": "Private",
                    }
                ],
            },
            {
                "totalSize": 1,
                "records": [
                    {
                        "ExternalSharingModel": "Read",
                        "InternalSharingModel": "ReadWrite",
                    }
                ],
            },
        ]
        task._post_deploy("Success")

        query = (
            "SELECT ExternalSharingModel, InternalSharingModel "
            "FROM EntityDefinition "
            "WHERE QualifiedApiName = '{}'"
        )

        task.sf.query.assert_has_calls(
            [
                mock.call(query.format("Account")),
                mock.call(query.format("Account")),
                mock.call(query.format("Test__c")),
            ]
        )

        assert task.poll_complete

    def test_post_deploy_waits_for_enablement__namespaced_org(self):
        task = create_task(
            SetOrgWideDefaults,
            {
                "managed": False,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": [
                    {
                        "api_name": "Account",
                        "internal_sharing_model": "Private",
                        "external_sharing_model": "Private",
                    },
                    {
                        "api_name": "Test__c",
                        "internal_sharing_model": "ReadWrite",
                        "external_sharing_model": "Read",
                    },
                ],
            },
        )
        task.org_config.namespaced = True
        task.project_config.project__package__namespace = "test"
        task.sf = mock.Mock()
        task.sf.query.side_effect = [
            {
                "totalSize": 1,
                "records": [
                    {"ExternalSharingModel": "Read", "InternalSharingModel": "Read"}
                ],
            },
            {
                "totalSize": 1,
                "records": [
                    {
                        "ExternalSharingModel": "Private",
                        "InternalSharingModel": "Private",
                    }
                ],
            },
            {
                "totalSize": 1,
                "records": [
                    {
                        "ExternalSharingModel": "Read",
                        "InternalSharingModel": "ReadWrite",
                    }
                ],
            },
        ]
        task._post_deploy("Success")

        query = (
            "SELECT ExternalSharingModel, InternalSharingModel "
            "FROM EntityDefinition "
            "WHERE QualifiedApiName = '{}'"
        )

        task.sf.query.assert_has_calls(
            [
                mock.call(query.format("Account")),
                mock.call(query.format("Account")),
                mock.call(query.format("test__Test__c")),
            ]
        )

        assert task.poll_complete

    def test_post_deploy_exception_not_found(self):
        task = create_task(
            SetOrgWideDefaults,
            {
                "managed": True,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": [
                    {
                        "api_name": "Account",
                        "internal_sharing_model": "Private",
                        "external_sharing_model": "Private",
                    }
                ],
            },
        )
        task.sf = mock.Mock()
        task.sf.query.return_value = {"totalSize": 0, "records": []}
        with pytest.raises(CumulusCIException):
            task._post_deploy("Success")

        query = (
            "SELECT ExternalSharingModel, InternalSharingModel "
            "FROM EntityDefinition "
            "WHERE QualifiedApiName = '{}'"
        )

        task.sf.query.assert_has_calls([mock.call(query.format("Account"))])

    def test_raises_exception_timeout(self):
        task = create_task(
            SetOrgWideDefaults,
            {
                "managed": True,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": [
                    {
                        "api_name": "Account",
                        "internal_sharing_model": "Private",
                        "external_sharing_model": "Private",
                    }
                ],
            },
        )

        task.time_start = datetime.min
        with pytest.raises(CumulusCIException):
            task._poll_action()

    def test_raises_exception_missing_values(self):
        with pytest.raises(TaskOptionsError):
            create_task(
                SetOrgWideDefaults,
                {
                    "managed": True,
                    "api_version": "47.0",
                    "api_names": "bar,foo",
                    "org_wide_defaults": [
                        {
                            "api_name": "Account",
                            "internal_sharing_model": "Private",
                            "external_sharing_model": "Private",
                        },
                        {"api_name": "Test__c"},
                    ],
                },
            )

    def test_raises_exception_bad_sharing_model(self):
        with pytest.raises(TaskOptionsError):
            create_task(
                SetOrgWideDefaults,
                {
                    "managed": True,
                    "api_version": "47.0",
                    "api_names": "bar,foo",
                    "org_wide_defaults": [
                        {
                            "api_name": "Account",
                            "internal_sharing_model": "Nonsense",
                            "external_sharing_model": "Private",
                        },
                        {"api_name": "Test__c"},
                    ],
                },
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_task(self, org_wide_defaults):
        return create_task(
            SetOrgWideDefaults,
            {
                "managed": True,
                "api_version": "47.0",
                "api_names": "bar,foo",
                "org_wide_defaults": org_wide_defaults,
            },
        )

    # ------------------------------------------------------------------
    # ControlledByParent constraint tests
    # ------------------------------------------------------------------

    def test_cbp_stop_flag_raises_on_mismatch(self):
        """stop_on_owd_sharing_model_mismatch=True always raises when CBP mismatch exists."""
        task = self._make_task(
            [
                {
                    "api_name": "Test__c",
                    "internal_sharing_model": "ControlledByParent",
                    "external_sharing_model": "Read",
                }
            ]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            True
        )
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML)

        with pytest.raises(CumulusCIException, match="ControlledByParent"):
            task._transform_entity(tree, "Test__c")

    def test_cbp_stop_flag_raises_when_only_internal_cbp_provided(self):
        """stop_on_owd_sharing_model_mismatch=True raises even when only internal is provided."""
        task = self._make_task(
            [{"api_name": "Test__c", "internal_sharing_model": "ControlledByParent"}]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            True
        )
        # Metadata starts with external=Read → will mismatch after internal is set to CBP.
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML)

        with pytest.raises(CumulusCIException, match="ControlledByParent"):
            task._transform_entity(tree, "Test__c")

    def test_cbp_only_internal_cbp_aligns_external(self):
        """User provides only internal=CBP; external should be auto-set to CBP."""
        task = self._make_task(
            [{"api_name": "Test__c", "internal_sharing_model": "ControlledByParent"}]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            False
        )
        # Metadata starts with sharingModel=Read, externalSharingModel=Read.
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML)

        result = task._transform_entity(tree, "Test__c")

        internal = result._element.findall(f".//{MD}sharingModel")
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(internal) == 1
        assert internal[0].text == "ControlledByParent"
        assert len(external) == 1
        assert external[0].text == "ControlledByParent"

    def test_cbp_only_internal_non_cbp_updates_external_cbp_to_default(self):
        """User provides only internal=ReadWrite; existing external=CBP → external set to default."""
        task = self._make_task(
            [{"api_name": "Test__c", "internal_sharing_model": "ReadWrite"}]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            False
        )
        task.project_config.project__git__settings__default_owd_sharing_model_when_controlled_by_parent = (
            "Private"
        )
        # Metadata has external=ControlledByParent, internal=Read.
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML_EXTERNAL_CBP)

        result = task._transform_entity(tree, "Test__c")

        internal = result._element.findall(f".//{MD}sharingModel")
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(internal) == 1
        assert internal[0].text == "ReadWrite"
        assert len(external) == 1
        assert external[0].text == "Private"

    def test_cbp_only_external_cbp_aligns_internal(self):
        """User provides only external=CBP; internal should be auto-set to CBP."""
        task = self._make_task(
            [{"api_name": "Test__c", "external_sharing_model": "ControlledByParent"}]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            False
        )
        # Metadata starts with sharingModel=Read, externalSharingModel=Read.
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML)

        result = task._transform_entity(tree, "Test__c")

        internal = result._element.findall(f".//{MD}sharingModel")
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(internal) == 1
        assert internal[0].text == "ControlledByParent"
        assert len(external) == 1
        assert external[0].text == "ControlledByParent"

    def test_cbp_only_external_non_cbp_updates_internal_cbp_to_default(self):
        """User provides only external=ReadWrite; existing internal=CBP → internal set to default."""
        task = self._make_task(
            [{"api_name": "Test__c", "external_sharing_model": "ReadWrite"}]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            False
        )
        task.project_config.project__git__settings__default_owd_sharing_model_when_controlled_by_parent = (
            "Private"
        )
        # Metadata has internal=ControlledByParent, external=Read.
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML_INTERNAL_CBP)

        result = task._transform_entity(tree, "Test__c")

        internal = result._element.findall(f".//{MD}sharingModel")
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(internal) == 1
        assert internal[0].text == "Private"
        assert len(external) == 1
        assert external[0].text == "ReadWrite"

    def test_cbp_both_cbp_no_change(self):
        """When both models are already CBP there is no mismatch and no change is made."""
        task = self._make_task(
            [
                {
                    "api_name": "Test__c",
                    "internal_sharing_model": "ControlledByParent",
                    "external_sharing_model": "ControlledByParent",
                }
            ]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            False
        )
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML_BOTH_CBP)

        result = task._transform_entity(tree, "Test__c")

        internal = result._element.findall(f".//{MD}sharingModel")
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(internal) == 1
        assert internal[0].text == "ControlledByParent"
        assert len(external) == 1
        assert external[0].text == "ControlledByParent"

    def test_cbp_both_provided_conflict_stop_flag_false_no_auto_correction(self):
        """Both values provided by user with a CBP conflict; stop_flag=False → no auto-correction,
        user values are applied as-is."""
        task = self._make_task(
            [
                {
                    "api_name": "Test__c",
                    "internal_sharing_model": "ControlledByParent",
                    "external_sharing_model": "Read",
                }
            ]
        )
        task.project_config.project__git__settings__stop_on_owd_sharing_model_mismatch = (
            False
        )
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML)

        result = task._transform_entity(tree, "Test__c")

        # No auto-correction: values stay exactly as the user specified.
        internal = result._element.findall(f".//{MD}sharingModel")
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(internal) == 1
        assert internal[0].text == "ControlledByParent"
        assert len(external) == 1
        assert external[0].text == "Read"

    def test_cbp_constraint_skipped_when_external_model_absent(self):
        """When the external model element is absent from metadata and the user does not supply it,
        the CBP constraint block is skipped entirely (line 100 branch → False)."""
        task = self._make_task(
            [{"api_name": "Test__c", "internal_sharing_model": "ReadWrite"}]
        )
        # Metadata has no externalSharingModel tag and user provides no external value;
        # external_model remains None after _transform_entity reads it.
        tree = metadata_tree.fromstring(CUSTOMOBJECT_XML_MISSING_TAGS)

        result = task._transform_entity(tree, "Test__c")

        internal = result._element.findall(f".//{MD}sharingModel")
        assert len(internal) == 1
        assert internal[0].text == "ReadWrite"
        # externalSharingModel was never created
        external = result._element.findall(f".//{MD}externalSharingModel")
        assert len(external) == 0

    def test_post_deploy_non_success_result_does_nothing(self):
        """_post_deploy with a result other than 'Success' must not poll or log."""
        task = self._make_task(
            [
                {
                    "api_name": "Account",
                    "internal_sharing_model": "Private",
                    "external_sharing_model": "Private",
                }
            ]
        )
        task.sf = mock.Mock()
        # Calling with a non-Success result should be a no-op (no exception, no query).
        task._post_deploy("Failed")
        task.sf.query.assert_not_called()
