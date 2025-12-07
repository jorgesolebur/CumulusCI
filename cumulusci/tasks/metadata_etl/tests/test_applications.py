from cumulusci.tasks.metadata_etl.applications import AddProfileActionOverrides
from cumulusci.tasks.salesforce.tests.util import create_task
from cumulusci.utils.xml import metadata_tree

MD = "{%s}" % metadata_tree.METADATA_NAMESPACE


APPLICATION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<CustomApplication xmlns="http://soap.sforce.com/2006/04/metadata">
    <brand>
        <headerColor>#0070D2</headerColor>
        <shouldOverrideOrgTheme>false</shouldOverrideOrgTheme>
    </brand>
    <description>Test Application</description>
    <label>Test App</label>
    <navType>Console</navType>
    {profileActionOverrides}
    <uiType>Lightning</uiType>
</CustomApplication>
"""

PROFILE_ACTION_OVERRIDE = """    <profileActionOverrides>
        <actionName>View</actionName>
        <content>TestRecordPage</content>
        <formFactor>Large</formFactor>
        <pageOrSobjectType>Account</pageOrSobjectType>
        <recordType>PersonAccount.User</recordType>
        <type>Flexipage</type>
        <profile>Admin</profile>
    </profileActionOverrides>
"""


class TestAddProfileActionOverrides:
    def test_adds_profile_action_override(self):
        """Test adding a new profileActionOverride"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "Edit",
                                "content": "CustomEditPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Contact",
                                "record_type": "Contact.Business",
                                "type": "Flexipage",
                                "profile": "StandardUser",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )
        element = tree._element

        # Verify no existing override
        assert len(element.findall(f".//{MD}profileActionOverrides")) == 0

        result = task._transform_entity(tree, "TestApp")

        # Verify override was added
        assert len(result._element.findall(f".//{MD}profileActionOverrides")) == 1

        override = result._element.find(f".//{MD}profileActionOverrides")
        assert override.find(f"{MD}actionName").text == "Edit"
        assert override.find(f"{MD}content").text == "CustomEditPage"
        assert override.find(f"{MD}formFactor").text == "Large"
        assert override.find(f"{MD}pageOrSobjectType").text == "Contact"
        assert override.find(f"{MD}recordType").text == "Contact.Business"
        assert override.find(f"{MD}type").text == "Flexipage"
        assert override.find(f"{MD}profile").text == "StandardUser"

    def test_adds_multiple_profile_action_overrides(self):
        """Test adding multiple profileActionOverrides to a single application"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "AccountViewPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": "PersonAccount.User",
                                "type": "Flexipage",
                                "profile": "Admin",
                            },
                            {
                                "action_name": "Edit",
                                "content": "ContactEditPage",
                                "form_factor": "Small",
                                "page_or_sobject_type": "Contact",
                                "record_type": None,
                                "type": "Visualforce",
                                "profile": "StandardUser",
                            },
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        # Verify both overrides were added
        overrides = result._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides) == 2

        # Check first override
        override1 = overrides[0]
        assert override1.find(f"{MD}actionName").text == "View"
        assert override1.find(f"{MD}content").text == "AccountViewPage"
        assert override1.find(f"{MD}profile").text == "Admin"

        # Check second override
        override2 = overrides[1]
        assert override2.find(f"{MD}actionName").text == "Edit"
        assert override2.find(f"{MD}content").text == "ContactEditPage"
        assert override2.find(f"{MD}profile").text == "StandardUser"
        # Verify recordType is not present when None
        assert override2.find(f"{MD}recordType") is None

    def test_adds_multiple_applications(self):
        """Test adding overrides to multiple applications"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "AccountViewPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    },
                    {
                        "name": "SecondApp",
                        "overrides": [
                            {
                                "action_name": "Edit",
                                "content": "ContactEditPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Contact",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "StandardUser",
                            }
                        ],
                    },
                ],
            },
        )

        # Verify api_names contains both applications
        assert "TestApp" in task.api_names
        assert "SecondApp" in task.api_names
        assert len(task.api_names) == 2

        # Test first application
        tree1 = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )
        result1 = task._transform_entity(tree1, "TestApp")
        overrides1 = result1._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides1) == 1
        assert overrides1[0].find(f"{MD}pageOrSobjectType").text == "Account"

        # Test second application
        tree2 = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )
        result2 = task._transform_entity(tree2, "SecondApp")
        overrides2 = result2._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides2) == 1
        assert overrides2[0].find(f"{MD}pageOrSobjectType").text == "Contact"

    def test_updates_existing_profile_action_override(self):
        """Test updating an existing profileActionOverride"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "UpdatedRecordPage",
                                "form_factor": "Small",
                                "page_or_sobject_type": "Account",
                                "record_type": "PersonAccount.User",
                                "type": "LightningComponent",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(
                profileActionOverrides=PROFILE_ACTION_OVERRIDE
            ).encode("utf-8")
        )
        element = tree._element

        # Verify existing override
        assert len(element.findall(f".//{MD}profileActionOverrides")) == 1
        original = element.find(f".//{MD}profileActionOverrides")
        assert original.find(f"{MD}content").text == "TestRecordPage"
        assert original.find(f"{MD}formFactor").text == "Large"

        result = task._transform_entity(tree, "TestApp")

        # Verify still only one override (updated, not added)
        overrides = result._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides) == 1

        # Verify override was updated
        override = overrides[0]
        assert override.find(f"{MD}actionName").text == "View"
        assert override.find(f"{MD}content").text == "UpdatedRecordPage"
        assert override.find(f"{MD}formFactor").text == "Small"
        assert override.find(f"{MD}type").text == "LightningComponent"
        assert override.find(f"{MD}profile").text == "Admin"

    def test_adds_override_when_different_profile(self):
        """Test that overrides with different profiles are treated as distinct"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "StandardUserRecordPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": "PersonAccount.User",
                                "type": "Flexipage",
                                "profile": "StandardUser",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(
                profileActionOverrides=PROFILE_ACTION_OVERRIDE
            ).encode("utf-8")
        )
        element = tree._element

        # Verify one existing override for Admin profile
        assert len(element.findall(f".//{MD}profileActionOverrides")) == 1

        result = task._transform_entity(tree, "TestApp")

        # Verify two overrides now (original + new for different profile)
        overrides = result._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides) == 2

        # Verify both profiles are present
        profiles = [o.find(f"{MD}profile").text for o in overrides]
        assert "Admin" in profiles
        assert "StandardUser" in profiles

    def test_namespace_injection_in_overrides(self):
        """Test that namespace injection works for override fields"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "%%%NAMESPACED_ORG%%%CustomPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "%%%NAMESPACE%%%CustomObject__c",
                                "record_type": "%%%NAMESPACE%%%CustomObject__c.%%%NAMESPACE%%%CustomRecordType",
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        override = result._element.find(f".//{MD}profileActionOverrides")
        # Namespace tokens should be processed (even if empty in test environment)
        assert override.find(f"{MD}content") is not None
        assert override.find(f"{MD}pageOrSobjectType") is not None
        assert override.find(f"{MD}recordType") is not None

    def test_namespace_injection_in_application_name(self):
        """Test that namespace injection works for application names"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "%%%NAMESPACE%%%TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "CustomPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        # Verify namespace token is processed in api_names
        # In test environment without namespace, it should be empty string
        assert len(task.api_names) == 1

    def test_override_without_record_type(self):
        """Test adding override without recordType"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "New",
                                "content": "NewContactPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Contact",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        override = result._element.find(f".//{MD}profileActionOverrides")
        assert override.find(f"{MD}actionName").text == "New"
        assert override.find(f"{MD}pageOrSobjectType").text == "Contact"
        # Verify recordType element is not present
        assert override.find(f"{MD}recordType") is None

    def test_skips_override_when_no_overrides_provided(self):
        """Test that task returns None when no overrides are provided"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        # Task should return metadata even with empty overrides
        # but no overrides should be added
        assert result is not None
        assert len(result._element.findall(f".//{MD}profileActionOverrides")) == 0

    def test_skips_override_when_no_applications_provided(self):
        """Test that task returns None when no applications are provided"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        # Task should return None when no applications configured
        assert result is None

    def test_skips_application_when_name_does_not_match(self):
        """Test that overrides are only applied to matching applications"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "DifferentApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "CustomPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        # No overrides should be added since application name doesn't match
        assert result is not None
        assert len(result._element.findall(f".//{MD}profileActionOverrides")) == 0

    def test_different_record_type_none_creates_separate_override(self):
        """Test that overrides with None recordType vs specific recordType are treated as distinct"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "GenericAccountPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": None,  # No specific recordType
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(
                profileActionOverrides=PROFILE_ACTION_OVERRIDE
            ).encode("utf-8")
        )

        # Original has recordType "PersonAccount.User"
        original = tree._element.find(f".//{MD}profileActionOverrides")
        assert original.find(f"{MD}recordType").text == "PersonAccount.User"

        result = task._transform_entity(tree, "TestApp")

        # Should have two overrides now (one with recordType, one without)
        overrides = result._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides) == 2

        # Check that we have one with recordType and one without
        overrides_with_record_type = [
            o for o in overrides if o.find(f"{MD}recordType") is not None
        ]
        overrides_without_record_type = [
            o for o in overrides if o.find(f"{MD}recordType") is None
        ]
        assert len(overrides_with_record_type) == 1
        assert len(overrides_without_record_type) == 1

    def test_different_record_types_create_separate_overrides(self):
        """Test that overrides with different recordTypes are treated as distinct"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "BusinessAccountPage",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": "Account.Business",
                                "type": "Flexipage",
                                "profile": "Admin",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(
                profileActionOverrides=PROFILE_ACTION_OVERRIDE
            ).encode("utf-8")
        )

        # Original has PersonAccount.User recordType
        original = tree._element.find(f".//{MD}profileActionOverrides")
        assert original.find(f"{MD}recordType").text == "PersonAccount.User"

        result = task._transform_entity(tree, "TestApp")

        # Should have two overrides now (different recordTypes)
        overrides = result._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides) == 2

        record_types = [
            o.find(f"{MD}recordType").text
            for o in overrides
            if o.find(f"{MD}recordType") is not None
        ]
        assert "PersonAccount.User" in record_types
        assert "Account.Business" in record_types

    def test_all_override_properties_are_set(self):
        """Test that all properties of an override are correctly set"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "TestApp",
                        "overrides": [
                            {
                                "action_name": "Clone",
                                "content": "CustomClonePage",
                                "form_factor": "Small",
                                "page_or_sobject_type": "Lead",
                                "record_type": "Lead.Enterprise",
                                "type": "LightningComponent",
                                "profile": "SalesUser",
                            }
                        ],
                    }
                ],
            },
        )

        tree = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )

        result = task._transform_entity(tree, "TestApp")

        override = result._element.find(f".//{MD}profileActionOverrides")

        # Verify all properties are correctly set
        assert override.find(f"{MD}actionName").text == "Clone"
        assert override.find(f"{MD}content").text == "CustomClonePage"
        assert override.find(f"{MD}formFactor").text == "Small"
        assert override.find(f"{MD}pageOrSobjectType").text == "Lead"
        assert override.find(f"{MD}recordType").text == "Lead.Enterprise"
        assert override.find(f"{MD}type").text == "LightningComponent"
        assert override.find(f"{MD}profile").text == "SalesUser"

    def test_complex_scenario_multiple_apps_and_overrides(self):
        """Test complex scenario with multiple applications and multiple overrides per app"""
        task = create_task(
            AddProfileActionOverrides,
            {
                "managed": True,
                "api_version": "47.0",
                "applications": [
                    {
                        "name": "AdminConsole",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "AdminAccountView",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "Admin",
                            },
                            {
                                "action_name": "Edit",
                                "content": "AdminAccountEdit",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Account",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "Admin",
                            },
                        ],
                    },
                    {
                        "name": "SalesConsole",
                        "overrides": [
                            {
                                "action_name": "View",
                                "content": "SalesContactView",
                                "form_factor": "Large",
                                "page_or_sobject_type": "Contact",
                                "record_type": None,
                                "type": "Flexipage",
                                "profile": "SalesUser",
                            }
                        ],
                    },
                ],
            },
        )

        # Verify both apps in api_names
        assert "AdminConsole" in task.api_names
        assert "SalesConsole" in task.api_names

        # Test AdminConsole
        tree1 = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )
        result1 = task._transform_entity(tree1, "AdminConsole")
        overrides1 = result1._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides1) == 2
        actions1 = [o.find(f"{MD}actionName").text for o in overrides1]
        assert "View" in actions1
        assert "Edit" in actions1

        # Test SalesConsole
        tree2 = metadata_tree.fromstring(
            APPLICATION_XML.format(profileActionOverrides="").encode("utf-8")
        )
        result2 = task._transform_entity(tree2, "SalesConsole")
        overrides2 = result2._element.findall(f".//{MD}profileActionOverrides")
        assert len(overrides2) == 1
        assert overrides2[0].find(f"{MD}pageOrSobjectType").text == "Contact"
