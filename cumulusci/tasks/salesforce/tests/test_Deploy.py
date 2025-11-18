import base64
import io
import os
import zipfile
from unittest import mock

import pytest

from cumulusci.core.config import BaseProjectConfig, UniversalConfig
from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.core.flowrunner import StepSpec
from cumulusci.core.source_transforms.transforms import CleanMetaXMLTransform
from cumulusci.tasks.salesforce import Deploy, DeployUnpackagedMetadata
from cumulusci.utils import temporary_dir, touch

from .util import create_task


class TestDeploy:
    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api(self, mock_org_config, rest_deploy):
        with temporary_dir() as path:
            touch("package.xml")
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "namespace_tokenize": "ns",
                    "namespace_inject": "ns",
                    "namespace_strip": "ns",
                    "unmanaged": True,
                    "rest_deply": rest_deploy,
                },
            )

            api = task._get_api()
            zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(api.package_zip)), "r")
            assert "package.xml" in zf.namelist()
            zf.close()

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    def test_create_api_object(self, mock_org_config):
        with temporary_dir() as path:
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "namespace_tokenize": "ns",
                    "namespace_inject": "ns",
                    "namespace_strip": "ns",
                    "unmanaged": True,
                    "collision_check": True,
                },
            )
            package_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <Package xmlns="http://soap.sforce.com/2006/04/metadata">
        <types>
            <members>Delivery__c.Supplier__c</members>
            <members>Delivery__c.Scheduled_Date__c</members>
            <name>CustomField</name>
        </types>
        <types>
            <name>CustomObject</name>
        </types>
        <types>
            <name>CustomTab</name>
        </types>
        <types>
            <name>Layout</name>
        </types>
        <types>
            <name>ListView</name>
        </types>
        <version>58.0</version>
    </Package>"""
            expected_package_xml = """<types><members>Delivery__c.Supplier__c</members><members>Delivery__c.Scheduled_Date__c</members><name>CustomField</name></types><types><name>CustomObject</name></types><types><name>CustomTab</name></types><types><name>Layout</name></types><types><name>ListView</name></types><version>58.0</version>    """
            api_object = task._create_api_object(package_xml, "58.0")

            assert api_object.package_xml.split() == expected_package_xml.split()
            assert api_object.api_version == "58.0"

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    def test_collision_check_positive(self, mock_org_config):
        with temporary_dir() as path:
            touch("package.xml")
            with open("package.xml", "w") as f:
                f.write(
                    """<?xml version="1.0" encoding="UTF-8"?>
    <Package xmlns="http://soap.sforce.com/2006/04/metadata">
        <types>
            <members>Delivery__c.Supplier__c</members>
            <members>Delivery__c.Scheduled_Date__c</members>
            <name>CustomField</name>
        </types>
        <types>
            <name>CustomObject</name>
        </types>
        <types>
            <name>CustomTab</name>
        </types>
        <types>
            <name>Layout</name>
        </types>
        <types>
            <name>ListView</name>
        </types>
        <version>58.0</version>
    </Package>"""
                )
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "namespace_tokenize": "ns",
                    "namespace_inject": "ns",
                    "namespace_strip": "ns",
                    "unmanaged": True,
                    "collision_check": True,
                },
            )

            task._create_api_object = mock.Mock(
                return_value=mock.Mock(
                    _get_response=mock.Mock(
                        return_value=mock.Mock(
                            content='<?xml version="1.0" encoding="UTF-8"?> <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns="http://soap.sforce.com/2006/04/metadata"><soapenv:Body><checkRetrieveStatusResponse><result><done>true</done><fileProperties><createdById>0051m0000069dpxAAA</createdById><createdByName>User User</createdByName><createdDate>2023-10-09T08:47:44.875Z</createdDate><fileName>unpackaged/package.xml</fileName><fullName>unpackaged/package.xml</fullName><id></id><lastModifiedById>0051m0000069dpxAAA</lastModifiedById><lastModifiedByName>User User</lastModifiedByName><lastModifiedDate>2023-10-09T08:47:44.875Z</lastModifiedDate><manageableState>unmanaged</manageableState><type>Package</type></fileProperties><id>09S1m000001EKBkEAO</id><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery_Item__c.Food_Expiration_Date__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery__c.Status__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery_Item__c.Food_Storage__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery_Item__c.Delivery__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery__c.Scheduled_Date__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery__c.Supplier__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomObject&apos; named &apos;Delivery__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomObject&apos; named &apos;Delivery_Item__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomTab&apos; named &apos;Delivery__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;Layout&apos; named &apos;Delivery_Item__c-Delivery Item Layout&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;Layout&apos; named &apos;Delivery__c-Delivery Layout&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;ListView&apos; named &apos;Delivery__c.All&apos; cannot be found</problem></messages><status>Succeeded</status><success>true</success><zipFile>UEsDBBQACAgIAPZFSVcAAAAAAAAAAAAAAAAWAAAAdW5wYWNrYWdlZC9wYWNrYWdlLnhtbKVTTU/DMAy991dUva8pCNCE0kyIUQkJCaQNrlGami2QNFXjwvrvyT7KuFTraE7Ji5/fsy3T2cbo8Atqp2yZRhdxEoVQSluocpVGr8tsMo1mLKAvQn6KFYQ+unRptEasbglxVlSxe7e1hFhaQy6T5IYkV8QAikKgiFgQ+kOxrcDt77u3AZN7STYHrbx2yx8RDOcy/gW4pKSLGsDLrC34w6ZStUBfCJ8LhH/lWKCtfZ1DuZ62kGsoGg3FWaJbIgps3DmEpqq0grqHUgoD7L5xaE2mQBeU7JD9BMifEQwex0BjJ8w85x8gcYSbkwpLkY8vdtIB4RYIn0RrGxzYgSO3n7bz132P6EV8p3V/fuXwTcF3v8Jh1dn1NE4o6V4BJYcNZ8EPUEsHCGtr2HwiAQAAEwQAAFBLAQIUABQACAgIAPZFSVdra9h8IgEAABMEAAAWAAAAAAAAAAAAAAAAAAAAAAB1bnBhY2thZ2VkL3BhY2thZ2UueG1sUEsFBgAAAAABAAEARAAAAGYBAAAAAA==</zipFile></result></checkRetrieveStatusResponse></soapenv:Body></soapenv:Envelope>'
                        )
                    )
                )
            )

            is_collision, xml_map = task._collision_check(path)

            assert is_collision is False
            print(xml_map)
            assert xml_map == {
                "CustomObject": [],
                "CustomTab": [],
                "Layout": [],
                "ListView": [],
            }

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    def test_collision_check_negative(self, mock_org_config):

        with temporary_dir() as path:
            touch("package.xml")
            with open("package.xml", "w") as f:
                f.write(
                    """<?xml version="1.0" encoding="UTF-8"?>
    <Package xmlns="http://soap.sforce.com/2006/04/metadata">
       <types>
            <members>Delivery__c.Supplier__c</members>
            <members>Delivery__c.Scheduled_Date__c</members>
            <name>CustomField</name>
        </types>
        <types>
            <name>CustomObject</name>
        </types>
        <types>
            <name>CustomTab</name>
        </types>
        <types>
            <name>Layout</name>
        </types>
        <types>
            <name>ListView</name>
        </types>
        <version>58.0</version>
    </Package>"""
                )
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "namespace_tokenize": "ns",
                    "namespace_inject": "ns",
                    "namespace_strip": "ns",
                    "unmanaged": True,
                    "collision_check": True,
                },
            )

            task._create_api_object = mock.Mock(
                return_value=mock.Mock(
                    _get_response=mock.Mock(
                        return_value=mock.Mock(
                            content='<?xml version="1.0" encoding="UTF-8"?> <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns="http://soap.sforce.com/2006/04/metadata"><soapenv:Body><checkRetrieveStatusResponse><result><done>true</done><fileProperties><createdById>0051m0000069dpxAAA</createdById><createdByName>User User</createdByName><createdDate>2023-10-09T08:47:44.875Z</createdDate><fileName>unpackaged/package.xml</fileName><fullName>unpackaged/package.xml</fullName><id></id><lastModifiedById>0051m0000069dpxAAA</lastModifiedById><lastModifiedByName>User User</lastModifiedByName><lastModifiedDate>2023-10-09T08:47:44.875Z</lastModifiedDate><manageableState>unmanaged</manageableState><type>Package</type></fileProperties><id>09S1m000001EKBkEAO</id><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery_Item__c.Food_Expiration_Date__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery__c.Status__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery_Item__c.Food_Storage__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery_Item__c.Delivery__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomField&apos; named &apos;Delivery__c.Supplier__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomObject&apos; named &apos;Delivery__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomObject&apos; named &apos;Delivery_Item__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;CustomTab&apos; named &apos;Delivery__c&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;Layout&apos; named &apos;Delivery_Item__c-Delivery Item Layout&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;Layout&apos; named &apos;Delivery__c-Delivery Layout&apos; cannot be found</problem></messages><messages><fileName>unpackaged/package.xml</fileName><problem>Entity of type &apos;ListView&apos; named &apos;Delivery__c.All&apos; cannot be found</problem></messages><status>Succeeded</status><success>true</success><zipFile>UEsDBBQACAgIAPZFSVcAAAAAAAAAAAAAAAAWAAAAdW5wYWNrYWdlZC9wYWNrYWdlLnhtbKVTTU/DMAy991dUva8pCNCE0kyIUQkJCaQNrlGami2QNFXjwvrvyT7KuFTraE7Ji5/fsy3T2cbo8Atqp2yZRhdxEoVQSluocpVGr8tsMo1mLKAvQn6KFYQ+unRptEasbglxVlSxe7e1hFhaQy6T5IYkV8QAikKgiFgQ+kOxrcDt77u3AZN7STYHrbx2yx8RDOcy/gW4pKSLGsDLrC34w6ZStUBfCJ8LhH/lWKCtfZ1DuZ62kGsoGg3FWaJbIgps3DmEpqq0grqHUgoD7L5xaE2mQBeU7JD9BMifEQwex0BjJ8w85x8gcYSbkwpLkY8vdtIB4RYIn0RrGxzYgSO3n7bz132P6EV8p3V/fuXwTcF3v8Jh1dn1NE4o6V4BJYcNZ8EPUEsHCGtr2HwiAQAAEwQAAFBLAQIUABQACAgIAPZFSVdra9h8IgEAABMEAAAWAAAAAAAAAAAAAAAAAAAAAAB1bnBhY2thZ2VkL3BhY2thZ2UueG1sUEsFBgAAAAABAAEARAAAAGYBAAAAAA==</zipFile></result></checkRetrieveStatusResponse></soapenv:Body></soapenv:Envelope>'
                        )
                    )
                )
            )

            is_collision, xml_map = task._collision_check(path)

            assert is_collision is True
            assert xml_map == {
                "CustomField": ["Delivery__c.Scheduled_Date__c"],
                "CustomObject": [],
                "CustomTab": [],
                "Layout": [],
                "ListView": [],
            }

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api__managed(self, mock_org_config, rest_deploy):
        with temporary_dir() as path:
            touch("package.xml")
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "namespace_inject": "ns",
                    "unmanaged": False,
                    "rest_deploy": rest_deploy,
                },
            )

            api = task._get_api()
            zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(api.package_zip)), "r")
            assert "package.xml" in zf.namelist()
            zf.close()

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api__additional_options(self, mock_org_config, rest_deploy):
        with temporary_dir() as path:
            touch("package.xml")
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "test_level": "RunSpecifiedTests",
                    "specified_tests": "TestA,TestB",
                    "unmanaged": False,
                    "rest_deploy": rest_deploy,
                },
            )

            api = task._get_api()
            assert api.run_tests == ["TestA", "TestB"]
            assert api.test_level == "RunSpecifiedTests"

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api__skip_clean_meta_xml(self, mock_org_config, rest_deploy):
        with temporary_dir() as path:
            touch("package.xml")
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "clean_meta_xml": False,
                    "unmanaged": True,
                    "rest_deploy": rest_deploy,
                },
            )

            api = task._get_api()
            zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(api.package_zip)), "r")
            assert "package.xml" in zf.namelist()
            zf.close()

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api__static_resources(self, mock_org_config, rest_deploy):
        with temporary_dir() as path:
            with open("package.xml", "w") as f:
                f.write(
                    """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <name>OtherType</name>
    </types>
</Package>"""
                )
                touch("otherfile")

            with temporary_dir() as static_resource_path:
                os.mkdir("TestBundle")
                touch("TestBundle/test.txt")
                touch("TestBundle.resource-meta.xml")

                task = create_task(
                    Deploy,
                    {
                        "path": path,
                        "static_resource_path": static_resource_path,
                        "namespace_tokenize": "ns",
                        "namespace_inject": "ns",
                        "namespace_strip": "ns",
                        "unmanaged": True,
                        "rest_deploy": rest_deploy,
                    },
                )

                api = task._get_api()
                zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(api.package_zip)), "r")
                namelist = zf.namelist()
                assert "staticresources/TestBundle.resource" in namelist
                assert "staticresources/TestBundle.resource-meta.xml" in namelist
                package_xml = zf.read("package.xml").decode()
                assert "<name>StaticResource</name>" in package_xml
                assert "<members>TestBundle</members>" in package_xml
                zf.close()

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api__missing_path(self, mock_org_config, rest_deploy):
        task = create_task(
            Deploy,
            {
                "path": "BOGUS",
                "unmanaged": True,
                "rest_deploy": rest_deploy,
            },
        )

        api = task._get_api()
        assert api is None

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_get_api__empty_package_zip(self, mock_org_config, rest_deploy):
        with temporary_dir() as path:
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "unmanaged": True,
                    "rest_deploy": rest_deploy,
                },
            )

            api = task._get_api()
            assert api is None

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    def test_get_api__collision_detected(self, mock_org_config):
        with temporary_dir() as path:
            task = create_task(
                Deploy,
                {
                    "path": path,
                    "namespace_tokenize": "ns",
                    "namespace_inject": "ns",
                    "namespace_strip": "ns",
                    "unmanaged": True,
                    "collision_check": True,
                },
            )
            task._get_package_zip = mock.Mock(return_value={"Custom Field": []})

            api = task._get_api()
            assert api is None

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_init_options(self, mock_org_config, rest_deploy):
        with pytest.raises(TaskOptionsError):
            create_task(
                Deploy,
                {
                    "path": "empty",
                    "test_level": "RunSpecifiedTests",
                    "unmanaged": False,
                    "rest_deploy": rest_deploy,
                },
            )

        with pytest.raises(TaskOptionsError):
            create_task(
                Deploy, {"path": "empty", "test_level": "Test", "unmanaged": False}
            )

        with pytest.raises(TaskOptionsError):
            create_task(
                Deploy,
                {
                    "path": "empty",
                    "test_level": "RunLocalTests",
                    "specified_tests": ["TestA"],
                    "unmanaged": False,
                    "rest_deploy": rest_deploy,
                },
            )

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_init_options__transforms(self, mock_org_config, rest_deploy):
        d = create_task(
            Deploy,
            {
                "path": "src",
                "transforms": ["clean_meta_xml"],
                "rest_deploy": rest_deploy,
            },
        )

        assert len(d.transforms) == 1
        assert isinstance(d.transforms[0], CleanMetaXMLTransform)

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_init_options__bad_transforms(self, mock_org_config, rest_deploy):
        with pytest.raises(TaskOptionsError) as e:
            create_task(
                Deploy,
                {
                    "path": "src",
                    "transforms": [{}],
                    "rest_deploy": rest_deploy,
                },
            )

            assert "transform spec is not valid" in str(e)

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_freeze_sets_kind(self, mock_org_config, rest_deploy):
        task = create_task(
            Deploy,
            {
                "path": "path",
                "namespace_tokenize": "ns",
                "namespace_inject": "ns",
                "namespace_strip": "ns",
                "rest_deploy": rest_deploy,
            },
        )
        step = StepSpec(
            step_num=1,
            task_name="deploy",
            task_config=task.task_config,
            task_class=None,
            project_config=task.project_config,
        )

        assert all(s["kind"] == "metadata" for s in task.freeze(step))


class TestDeployUnpackagedMetadata:
    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    def test_task_options_excludes_path(self, mock_org_config):
        """Test that path is removed from task_options."""
        assert "path" not in DeployUnpackagedMetadata.task_options
        # Verify other options are still present
        assert "check_only" in DeployUnpackagedMetadata.task_options
        assert "namespace_inject" in DeployUnpackagedMetadata.task_options

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    def test_init_options_sets_path_from_consolidate_metadata(
        self, mock_consolidate, mock_org_config
    ):
        """Test that _init_options sets path using consolidate_metadata."""
        with temporary_dir() as path:
            mock_consolidate.return_value = (path, 1)
            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            task = create_task(
                DeployUnpackagedMetadata,
                {"unmanaged": True},
                project_config=project_config,
            )

            mock_consolidate.assert_called_once_with("unpackaged/pre", path)
            assert task.options["path"] == path

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    def test_init_options_calls_consolidate_metadata_with_correct_params(
        self, mock_consolidate, mock_org_config
    ):
        """Test that consolidate_metadata is called with correct parameters."""
        with temporary_dir() as path:
            consolidated_path = os.path.join(path, "consolidated")
            os.makedirs(consolidated_path)
            mock_consolidate.return_value = (consolidated_path, 5)

            repo_root = "/repo/root"
            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": repo_root},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            task = create_task(
                DeployUnpackagedMetadata,
                {"unmanaged": True},
                project_config=project_config,
            )

            mock_consolidate.assert_called_once_with("unpackaged/pre", repo_root)
            assert task.options["path"] == consolidated_path

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    @mock.patch("cumulusci.tasks.salesforce.Deploy.clean_temp_directory")
    def test_run_task_calls_parent_and_cleans_up(
        self, mock_clean_temp, mock_consolidate, mock_org_config
    ):
        """Test that _run_task calls parent's _run_task and cleans up."""
        with temporary_dir() as path:
            touch("package.xml")
            consolidated_path = os.path.join(path, "consolidated")
            os.makedirs(consolidated_path)
            mock_consolidate.return_value = (consolidated_path, 3)

            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            task = create_task(
                DeployUnpackagedMetadata,
                {"unmanaged": True},
                project_config=project_config,
            )

            # Mock parent's _run_task to avoid actual deployment
            task._get_api = mock.Mock(return_value=mock.Mock())
            task._run_task()

            # Verify cleanup was called
            mock_clean_temp.assert_called_once_with(consolidated_path)

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    @mock.patch("cumulusci.tasks.salesforce.Deploy.clean_temp_directory")
    def test_run_task_cleans_up_on_exception(
        self, mock_clean_temp, mock_consolidate, mock_org_config
    ):
        """Test that cleanup happens even when parent's _run_task raises exception."""
        with temporary_dir() as path:
            consolidated_path = os.path.join(path, "consolidated")
            os.makedirs(consolidated_path)
            mock_consolidate.return_value = (consolidated_path, 2)

            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            task = create_task(
                DeployUnpackagedMetadata,
                {"unmanaged": True},
                project_config=project_config,
            )

            # Mock parent's _run_task to raise an exception
            task._get_api = mock.Mock(side_effect=Exception("Test exception"))

            with pytest.raises(Exception, match="Test exception"):
                task._run_task()

            # Verify cleanup was still called despite exception
            mock_clean_temp.assert_called_once_with(consolidated_path)

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    def test_init_options_inherits_parent_options(
        self, mock_consolidate, mock_org_config
    ):
        """Test that _init_options properly calls parent's _init_options."""
        with temporary_dir() as path:
            consolidated_path = os.path.join(path, "consolidated")
            os.makedirs(consolidated_path)
            mock_consolidate.return_value = (consolidated_path, 4)

            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            task = create_task(
                DeployUnpackagedMetadata,
                {
                    "unmanaged": True,
                    "check_only": True,
                    "test_level": "RunLocalTests",
                },
                project_config=project_config,
            )

            # Verify parent options were processed
            assert task.check_only is True
            assert task.test_level == "RunLocalTests"
            # Verify path was set from consolidate_metadata
            assert task.options["path"] == consolidated_path

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    @pytest.mark.parametrize("rest_deploy", [True, False])
    def test_inherits_rest_deploy_option(
        self, mock_consolidate, mock_org_config, rest_deploy
    ):
        """Test that rest_deploy option is properly inherited from parent."""
        with temporary_dir() as path:
            consolidated_path = os.path.join(path, "consolidated")
            os.makedirs(consolidated_path)
            mock_consolidate.return_value = (consolidated_path, 6)

            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            task = create_task(
                DeployUnpackagedMetadata,
                {"unmanaged": True, "rest_deploy": rest_deploy},
                project_config=project_config,
            )

            assert task.rest_deploy == rest_deploy

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    @mock.patch("cumulusci.tasks.salesforce.Deploy.consolidate_metadata")
    def test_no_unpackaged_metadata_path(self, mock_consolidate, mock_org_config):
        """Test that when unpackaged_metadata_path is None, consolidate_metadata is not called and path is not set."""
        with temporary_dir() as path:
            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = None

            task = create_task(
                DeployUnpackagedMetadata,
                {},
                project_config=project_config,
            )

            # Verify consolidate_metadata was not called
            mock_consolidate.assert_not_called()
            # When unpackaged_metadata_path is None, _init_options returns early
            # so parent's _init_options is not called and options may not be initialized
            # or path is not set if options exists
            if hasattr(task, "options"):
                assert "path" not in task.options

    @mock.patch(
        "cumulusci.core.config.org_config.OrgConfig.installed_packages", return_value=[]
    )
    def test_consolidate_metadata_integration(self, mock_org_config):
        """Integration test that actually calls consolidate_metadata without mocking."""
        with temporary_dir() as path:
            # Create a realistic metadata structure
            metadata_dir = os.path.join(path, "unpackaged", "pre")
            os.makedirs(metadata_dir)

            # Create package.xml
            package_xml_path = os.path.join(metadata_dir, "package.xml")
            with open(package_xml_path, "w") as f:
                f.write(
                    """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>*</members>
        <name>ApexClass</name>
    </types>
    <version>60.0</version>
</Package>"""
                )

            # Create some metadata files
            classes_dir = os.path.join(metadata_dir, "classes")
            os.makedirs(classes_dir)

            # Create an Apex class
            with open(os.path.join(classes_dir, "TestClass.cls"), "w") as f:
                f.write("public class TestClass { }")

            # Create an Apex class metadata file
            with open(os.path.join(classes_dir, "TestClass.cls-meta.xml"), "w") as f:
                f.write(
                    """<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <status>Active</status>
</ApexClass>"""
                )

            universal_config = UniversalConfig()
            project_config = BaseProjectConfig(
                universal_config,
                config={"noyaml": True, "project": {"package": {}}},
                repo_info={"root": path},
            )
            project_config.project__package__unpackaged_metadata_path = "unpackaged/pre"

            # Create task without mocking consolidate_metadata
            task = create_task(
                DeployUnpackagedMetadata,
                {"unmanaged": True},
                project_config=project_config,
            )

            # Verify that path was set to a temporary directory (not the original)
            assert task.options["path"] != metadata_dir
            # The path should exist
            assert os.path.exists(task.options["path"])
            # The consolidated path should contain our files
            consolidated_package_xml = os.path.join(task.options["path"], "package.xml")
            assert os.path.exists(consolidated_package_xml)
            # Verify the consolidated directory contains the classes directory
            consolidated_classes_dir = os.path.join(task.options["path"], "classes")
            assert os.path.exists(consolidated_classes_dir)
            # Verify our test class exists in consolidated directory
            assert os.path.exists(
                os.path.join(consolidated_classes_dir, "TestClass.cls")
            )
            assert os.path.exists(
                os.path.join(consolidated_classes_dir, "TestClass.cls-meta.xml")
            )
