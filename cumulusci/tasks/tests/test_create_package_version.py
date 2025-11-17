import io
import json
import os
import pathlib
import re
import shutil
import zipfile
from unittest import mock

import pytest
import responses
import yaml
from pydantic.v1 import ValidationError

from cumulusci.core.config import BaseProjectConfig, TaskConfig, UniversalConfig
from cumulusci.core.dependencies.dependencies import (
    PackageNamespaceVersionDependency,
    PackageVersionIdDependency,
)
from cumulusci.core.dependencies.github import UnmanagedGitHubRefDependency
from cumulusci.core.exceptions import (
    CumulusCIUsageError,
    DependencyLookupError,
    GithubException,
    PackageUploadFailure,
    TaskOptionsError,
    VcsException,
)
from cumulusci.core.keychain import BaseProjectKeychain
from cumulusci.salesforce_api.package_zip import BasePackageZipBuilder
from cumulusci.tasks.create_package_version import (
    PERSISTENT_ORG_ERROR,
    CreatePackageVersion,
    PackageConfig,
    PackageTypeEnum,
    VersionTypeEnum,
)
from cumulusci.tests.util import CURRENT_SF_API_VERSION
from cumulusci.utils import temporary_dir, touch

print(CURRENT_SF_API_VERSION)


@pytest.fixture
def repo_root():
    with temporary_dir() as path:
        os.mkdir(".git")
        os.mkdir("src")
        pathlib.Path(path, "src", "package.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n<Package xmlns="http://soap.sforce.com/2006/04/metadata"></Package>'
        )
        with open("cumulusci.yml", "w") as f:
            yaml.dump(
                {
                    "project": {
                        "dependencies": [
                            {"namespace": "pub", "version": "1.5"},
                            {
                                "repo_owner": "SalesforceFoundation",
                                "repo_name": "EDA",
                                "ref": "aaaaa",
                                "subfolder": "unpackaged/pre/first",
                            },
                            {
                                "namespace": "hed",
                                "version": "1.99",
                            },
                        ]
                    }
                },
                f,
            )
        pathlib.Path(path, "unpackaged", "pre", "first").mkdir(parents=True)
        touch(os.path.join("unpackaged", "pre", "first", "package.xml"))
        yield path


@pytest.fixture
def project_config(repo_root):
    project_config = BaseProjectConfig(
        UniversalConfig(),
        repo_info={"root": repo_root, "branch": "main"},
    )
    project_config.config["project"]["package"]["install_class"] = "Install"
    project_config.config["project"]["package"]["uninstall_class"] = "Uninstall"
    project_config.keychain = BaseProjectKeychain(project_config, key=None)
    pathlib.Path(repo_root, "orgs").mkdir()
    pathlib.Path(repo_root, "orgs", "scratch_def.json").write_text(
        json.dumps(
            {
                "edition": "Developer",
                "settings": {},
            }
        )
    )

    return project_config


@pytest.fixture
def get_task(project_config, devhub_config, org_config):
    def _get_task(options=None):
        opts = options or {
            "package_type": "Managed",
            "org_dependent": False,
            "package_name": "Test Package",
            "static_resource_path": "static-resources",
            "ancestor_id": "04t000000000000",
            "create_unlocked_dependency_packages": True,
            "install_key": "foo",
        }
        task = CreatePackageVersion(
            project_config,
            TaskConfig({"options": opts}),
            org_config,
        )
        with mock.patch(
            "cumulusci.tasks.create_package_version.get_devhub_config",
            return_value=devhub_config,
        ):
            task._init_task()
        return task

    return _get_task


@pytest.fixture
def task(get_task):
    return get_task()


@pytest.fixture
def mock_download_extract_github():
    with mock.patch(
        "cumulusci.core.dependencies.base.UnmanagedVcsDependency._get_zip_src"
    ) as download_extract_github:
        yield download_extract_github


@pytest.fixture
def mock_get_static_dependencies():
    with mock.patch(
        "cumulusci.tasks.create_package_version.get_static_dependencies"
    ) as get_static_dependencies:
        get_static_dependencies.return_value = [
            PackageNamespaceVersionDependency(namespace="pub", version="1.5"),
            UnmanagedGitHubRefDependency(
                repo_owner="SalesforceFoundation",
                repo_name="EDA",
                subfolder="unpackaged/pre/first",
                ref="abcdef",
            ),
            PackageNamespaceVersionDependency(namespace="hed", version="1.99"),
        ]
        yield get_static_dependencies


class TestPackageConfig:
    def test_org_config(self, project_config, org_config):
        org_config.config_file = None
        with pytest.raises(
            TaskOptionsError,
            match=PERSISTENT_ORG_ERROR,
        ):
            CreatePackageVersion(project_config, TaskConfig(), org_config)

    def test_validate_org_dependent(self):
        with pytest.raises(ValidationError, match="Only unlocked packages"):
            PackageConfig(package_type=PackageTypeEnum.managed, org_dependent=True)  # type: ignore

    def test_validate_post_install_script(self):
        with pytest.raises(ValidationError, match="Only managed packages"):
            PackageConfig(
                package_type=PackageTypeEnum.unlocked, post_install_script="Install"
            )  # type: ignore

    def test_validate_uninstall_script(self):
        with pytest.raises(ValidationError, match="Only managed packages"):
            PackageConfig(
                package_type=PackageTypeEnum.unlocked, uninstall_script="Uninstall"
            )  # type: ignore


class TestCreatePackageVersion:
    devhub_base_url = (
        f"https://devhub.my.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}"
    )
    scratch_base_url = (
        f"https://scratch.my.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}"
    )

    def test_postinstall_script_logic(self, get_task):
        task = get_task({"package_type": "Managed", "package_name": "Foo"})

        # Values set in the fixture project_config above
        assert task.package_config.post_install_script == "Install"
        assert task.package_config.uninstall_script == "Uninstall"

        task = get_task(
            {
                "package_type": "Unlocked",
                "package_name": "Foo",
                "post_install_script": None,
                "uninstall_script": None,
            }
        )

        assert task.package_config.post_install_script is None
        assert task.package_config.uninstall_script is None

    @responses.activate
    def test_run_task(
        self,
        task,
        mock_download_extract_github,
        mock_get_static_dependencies,
        devhub_config,
    ):
        zf = zipfile.ZipFile(io.BytesIO(), "w")
        zf.writestr("unpackaged/pre/first/package.xml", "")
        mock_download_extract_github.return_value = zf
        # _get_or_create_package() responses
        responses.add(  # query to find existing package
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )
        responses.add(  # create Package2
            "POST",
            f"{self.devhub_base_url}/tooling/sobjects/Package2/",
            json={"id": "0Ho6g000000fy4ZCAQ"},
        )

        # _resolve_ancestor_id() responses
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Id": "05i000000000000"}]},
        )

        # _create_version_request() responses
        responses.add(  # query to find existing Package2VersionCreateRequest
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )
        responses.add(  # query to find base version
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "04t000000000002AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "BuildNumber": 1,
                        "IsReleased": False,
                    }
                ],
            },
        )
        responses.add(  # get dependency org API version
            "GET",
            "https://scratch.my.salesforce.com/services/data",
            json=[{"version": CURRENT_SF_API_VERSION}],
        )
        responses.add(  # query for dependency org installed packages
            "GET",
            f"{self.scratch_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "SubscriberPackage": {
                            "Id": "033000000000002AAA",
                            "NamespacePrefix": "pub",
                        },
                        "SubscriberPackageVersionId": "04t000000000002AAA",
                    },
                    {
                        "SubscriberPackage": {
                            "Id": "033000000000003AAA",
                            "NamespacePrefix": "hed",
                        },
                        "SubscriberPackageVersionId": "04t000000000003AAA",
                    },
                ],
            },
        )
        # query dependency org for installed package 1
        responses.add(
            "GET",
            f"{self.scratch_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "04t000000000002AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 5,
                        "PatchVersion": 0,
                        "BuildNumber": 1,
                        "IsBeta": False,
                    }
                ],
            },
        )
        responses.add(  # query dependency org for installed package 2)
            "GET",
            f"{self.scratch_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "04t000000000003AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 99,
                        "PatchVersion": 0,
                        "BuildNumber": 1,
                        "IsBeta": False,
                    }
                ],
            },
        )
        responses.add(  # query for existing package (dependency from github)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {"Id": "0Ho000000000001AAA", "ContainerOptions": "Unlocked"}
                ],
            },
        )
        responses.add(  # query for existing package version (dependency from github)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Id": "08c000000000001AAA"}]},
        )
        responses.add(  # check status of Package2VersionCreateRequest (dependency from github)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "08c000000000001AAA",
                        "Status": "Success",
                        "Package2VersionId": "051000000000001AAA",
                    }
                ],
            },
        )
        responses.add(  # get info from Package2Version (dependency from github)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "SubscriberPackageVersionId": "04t000000000001AAA",
                        "MajorVersion": 0,
                        "MinorVersion": 1,
                        "PatchVersion": 0,
                        "BuildNumber": 1,
                    }
                ],
            },
        )
        responses.add(  # query for existing package (unpackaged/pre)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {"Id": "0Ho000000000004AAA", "ContainerOptions": "Unlocked"}
                ],
            },
        )
        responses.add(  # query for existing package version (unpackaged/pre)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Id": "08c000000000004AAA"}]},
        )
        responses.add(  # check status of Package2VersionCreateRequest (unpackaged/pre)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "08c000000000004AAA",
                        "Status": "Success",
                        "Package2VersionId": "051000000000004AAA",
                    }
                ],
            },
        )
        responses.add(  # get info from Package2Version (unpackaged/pre)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "SubscriberPackageVersionId": "04t000000000004AAA",
                        "MajorVersion": 0,
                        "MinorVersion": 1,
                        "PatchVersion": 0,
                        "BuildNumber": 1,
                    }
                ],
            },
        )
        responses.add(  # create Package2VersionCreateRequest (main package)
            "POST",
            f"{self.devhub_base_url}/tooling/sobjects/Package2VersionCreateRequest/",
            json={"id": "08c000000000002AAA"},
        )
        responses.add(  # check status of Package2VersionCreateRequest (main package)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "08c000000000002AAA",
                        "Status": "Success",
                        "Package2VersionId": "051000000000002AAA",
                    }
                ],
            },
        )
        responses.add(  # get info from Package2Version (main package)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "SubscriberPackageVersionId": "04t000000000002AAA",
                        "MajorVersion": 1,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "BuildNumber": 1,
                    }
                ],
            },
        )
        responses.add(  # get dependencies from SubscriberPackageVersion (main package)
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Dependencies": {
                            "ids": [
                                {"subscriberPackageVersionId": "04t000000000009AAA"}
                            ]
                        }
                    }
                ],
            },
        )

        with mock.patch(
            "cumulusci.tasks.create_package_version.get_devhub_config",
            return_value=devhub_config,
        ):
            task()
        zf.close()
        assert task.return_values["dependencies"] == [
            {"version_id": "04t000000000009AAA"}
        ]
        assert task.return_values["install_key"] == task.options["install_key"]
        zf.close()

    @responses.activate
    def test_get_or_create_package__namespaced_existing(
        self, project_config, devhub_config, org_config
    ):
        responses.add(  # query to find existing package
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {"Id": "0Ho6g000000fy4ZCAQ", "ContainerOptions": "Managed"}
                ],
            },
        )

        task = CreatePackageVersion(
            project_config,
            TaskConfig(
                {
                    "options": {
                        "package_type": "Managed",
                        "package_name": "Test Package",
                        "namespace": "ns",
                    }
                }
            ),
            org_config,
        )

        with mock.patch(
            "cumulusci.tasks.create_package_version.get_devhub_config",
            return_value=devhub_config,
        ):
            task._init_task()

        result = task._get_or_create_package(task.package_config)
        assert result == "0Ho6g000000fy4ZCAQ"

    @responses.activate
    def test_get_or_create_package__exists_but_wrong_type(
        self, project_config, devhub_config, org_config
    ):
        responses.add(  # query to find existing package
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {"Id": "0Ho6g000000fy4ZCAQ", "ContainerOptions": "Unlocked"}
                ],
            },
        )

        task = CreatePackageVersion(
            project_config,
            TaskConfig(
                {
                    "options": {
                        "package_type": "Managed",
                        "package_name": "Test Package",
                        "namespace": "ns",
                    }
                }
            ),
            org_config,
        )
        with mock.patch(
            "cumulusci.tasks.create_package_version.get_devhub_config",
            return_value=devhub_config,
        ):
            task._init_task()
        with pytest.raises(PackageUploadFailure):
            task._get_or_create_package(task.package_config)

    @responses.activate
    def test_get_or_create_package__devhub_disabled(self, task):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json=[{"message": "Object type 'Package2' is not supported"}],
            status=400,
        )

        with pytest.raises(TaskOptionsError):
            task._get_or_create_package(task.package_config)

    @responses.activate
    def test_get_or_create_package__multiple_existing(self, task):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 2, "records": []},
        )

        with pytest.raises(TaskOptionsError):
            task._get_or_create_package(task.package_config)

    @responses.activate
    def test_create_version_request__existing_package_version(self, task):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Id": "08c000000000001AAA"}]},
        )

        builder = BasePackageZipBuilder()
        result = task._create_version_request(
            "0Ho6g000000fy4ZCAQ", task.package_config, builder
        )
        assert result == "08c000000000001AAA"

    def test_has_1gp_namespace_dependencies__no(self, task):
        assert not task._has_1gp_namespace_dependency([])

    def test_has_1gp_namespace_dependencies__transitive(self, task):
        assert task._has_1gp_namespace_dependency(
            [PackageNamespaceVersionDependency(namespace="foo", version="1.5")]
        )

    def test_convert_project_dependencies__unrecognized_format(self, task):
        with pytest.raises(DependencyLookupError):
            task._convert_project_dependencies([{"foo": "bar"}])

    def test_convert_project_dependencies__no_unlocked_packages(self, task):
        task.options["create_unlocked_dependency_packages"] = False
        assert task._convert_project_dependencies(
            [
                PackageVersionIdDependency(version_id="04t000000000000"),
                UnmanagedGitHubRefDependency(
                    github="https://github.com/test/test", ref="abcdef"
                ),
            ]
        ) == [{"subscriberPackageVersionId": "04t000000000000"}]

    def test_unpackaged_pre_dependencies__none(self, task):
        shutil.rmtree(str(pathlib.Path(task.project_config.repo_root, "unpackaged")))

        assert task._get_unpackaged_pre_dependencies([]) == []

    def test_unpackaged_pre_dependencies__no_unlocked_packages(self, task):
        task.options["create_unlocked_dependency_packages"] = False

        assert task._get_unpackaged_pre_dependencies([]) == []

    @responses.activate
    def test_poll_action__error(self, task):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "08c000000000002AAA", "Status": "Error"}],
            },
        )
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Message": "message"}]},
        )

        task.request_id = "08c000000000002AAA"
        with pytest.raises(PackageUploadFailure) as err:
            task._poll_action()
        assert "message" in str(err)

    @responses.activate
    def test_poll_action__other(self, task):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [{"Id": "08c000000000002AAA", "Status": "InProgress"}],
            },
        )

        task.request_id = "08c000000000002AAA"
        task._poll_action()

    @responses.activate
    def test_get_base_version_number__fallback(self, task):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        version = task._get_base_version_number(None, "0Ho6g000000fy4ZCAQ")
        assert version.format() == "0.0.0.0"

    @responses.activate
    def test_get_base_version_number__from_github(self, task):
        task.project_config.get_latest_version = mock.Mock(return_value="1.0.0.1")

        version = task._get_base_version_number(
            "latest_github_release", "0Ho6g000000fy4ZCAQ"
        )
        assert version.format() == "1.0.0.1"

    @responses.activate
    def test_get_base_version_number__from_github_1gp(self, task):
        task.project_config.get_latest_version = mock.Mock(return_value="1.0.0")

        version = task._get_base_version_number(
            "latest_github_release", "0Ho6g000000fy4ZCAQ"
        )
        assert version.format() == "1.0.0.0"

    @responses.activate
    def test_get_base_version_number__from_github_1gp_2_figures(self, task):
        task.project_config.get_latest_version = mock.Mock(return_value="1.0")

        version = task._get_base_version_number(
            "latest_github_release", "0Ho6g000000fy4ZCAQ"
        )
        assert version.format() == "1.0.0.0"

    @responses.activate
    def test_get_base_version_number__from_github_1gp_beta(self, task):
        # This shouldn't happen unless the project is misconfigured,
        # but we'll ensure we handle it gracefully.
        task.project_config.get_latest_version = mock.Mock(return_value="1.0 (Beta 2)")

        version = task._get_base_version_number(
            "latest_github_release", "0Ho6g000000fy4ZCAQ"
        )
        assert version.format() == "1.0.0.2"

    @responses.activate
    def test_get_base_version_number__from_github__no_release(self, task):
        task.project_config.get_latest_version = mock.Mock(side_effect=GithubException)

        version = task._get_base_version_number(
            "latest_github_release", "0Ho6g000000fy4ZCAQ"
        )
        assert version.format() == "0.0.0.0"

    @responses.activate
    def test_get_base_version_number__explicit(self, task):
        version = task._get_base_version_number("1.0.0.1", "0Ho6g000000fy4ZCAQ")
        assert version.format() == "1.0.0.1"

    @responses.activate
    def test_increment_major_version__no_version_base_specified(self, task):
        """Test incrementing version from 0.0.0.12 -> 1.0.0.0"""
        responses.add(  # query to find base version
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={
                "size": 1,
                "records": [
                    {
                        "Id": "04t000000000002AAA",
                        "MajorVersion": 0,
                        "MinorVersion": 0,
                        "PatchVersion": 0,
                        "BuildNumber": 12,
                        "IsReleased": False,
                    }
                ],
            },
        )
        version_base = None
        version = task._get_base_version_number(version_base, "a package 2 Id")
        next_version = version.increment(VersionTypeEnum.major)
        assert next_version.format() == "1.0.0.NEXT"

    @responses.activate
    @mock.patch("cumulusci.tasks.create_package_version.get_version_id_from_tag")
    @mock.patch("cumulusci.tasks.create_package_version.get_latest_tag")
    @mock.patch("cumulusci.tasks.create_package_version.get_repo_from_config")
    def test_resolve_ancestor_id__latest_github_release(
        self, get_repo_from_config, get_latest_tag, get_version_id_from_tag, task
    ):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Id": "05i000000000000"}]},
        )

        project_config = mock.Mock()
        task.project_config = project_config

        # Mock the repo object
        mock_repo = mock.Mock()
        get_repo_from_config.return_value = mock_repo
        get_latest_tag.return_value = "v1.0.0"
        get_version_id_from_tag.return_value = "04t000000000111"

        actual_id = task._resolve_ancestor_id("latest_github_release")
        assert actual_id == "05i000000000000"

    @responses.activate
    def test_resolve_ancestor_id__no_ancestor_specified(self, task):
        project_config = mock.Mock()
        project_config.get_latest_tag.side_effect = GithubException
        task.project_config = project_config

        assert task._resolve_ancestor_id() == ""

    @responses.activate
    @mock.patch("cumulusci.tasks.create_package_version.get_version_id_from_tag")
    def test_resolve_ancestor_id__ancestor_explicitly_specified(
        self, get_version_id_from_tag, task
    ):
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 1, "records": [{"Id": "05i000000000000"}]},
        )

        project_config = mock.Mock()
        task.project_config = project_config

        get_version_id_from_tag.return_value = "04t000000000111"

        actual_id = task._resolve_ancestor_id("04t000000000000")
        assert actual_id == "05i000000000000"

    @responses.activate
    @mock.patch("cumulusci.tasks.create_package_version.get_latest_tag")
    @mock.patch("cumulusci.tasks.create_package_version.get_repo_from_config")
    def test_resolve_ancestor_id__no_release_found(
        self, get_repo_from_config, get_latest_tag, task
    ):
        project_config = mock.Mock()
        project_config.get_latest_tag.side_effect = GithubException
        task.project_config = project_config

        # Mock the repo object
        mock_repo = mock.Mock()
        get_repo_from_config.return_value = mock_repo
        get_latest_tag.side_effect = VcsException("No release found")

        assert task._resolve_ancestor_id("latest_github_release") == ""

    def test_resolve_ancestor_id__unlocked_package(self, task):
        task.package_config = PackageConfig(
            package_name="test_package",
            package_type="Unlocked",
            org_dependent=False,
            post_install_script=None,
            uninstall_script=None,
            namespace="test",
            version_name="Release",
            version_base=None,
            version_type="patch",
        )
        with pytest.raises(
            CumulusCIUsageError,
            match="Cannot specify an ancestor for Unlocked packages.",
        ):
            task._resolve_ancestor_id("04t000000000000")

    def test_resolve_ancestor_id__invalid_option_value(self, task):
        with pytest.raises(
            TaskOptionsError,
            match=re.escape("Unrecognized value for ancestor_id: 001001001001001"),
        ):
            task._resolve_ancestor_id("001001001001001")

    def test_prepare_cci_dependencies(self, task):
        assert task._prepare_cci_dependencies("") == []
        assert task._prepare_cci_dependencies(None) == []
        assert task._prepare_cci_dependencies(
            {"ids": [{"subscriberPackageVersionId": "04t000000000000"}]}
        ) == [{"version_id": "04t000000000000"}]


class TestPackageConfigNewFeatures:
    """Tests for new PackageConfig validation features."""

    def test_validate_apex_test_access(self):
        with pytest.raises(ValidationError, match="Only managed packages"):
            PackageConfig(
                package_type=PackageTypeEnum.unlocked,
                apex_test_access={"permission_set_names": ["TestPermSet"]},
            )  # type: ignore

    def test_validate_package_metadata_access(self):
        with pytest.raises(ValidationError, match="Only managed packages"):
            PackageConfig(
                package_type=PackageTypeEnum.unlocked,
                package_metadata_access={"permission_set_names": ["TestPermSet"]},
            )  # type: ignore


class TestCreatePackageVersionNewFeatures:
    """Tests for new CreatePackageVersion functionality."""

    devhub_base_url = (
        f"https://devhub.my.salesforce.com/services/data/v{CURRENT_SF_API_VERSION}"
    )

    @responses.activate
    def test_version_number_option(self, get_task, devhub_config):
        """Test that version_number option is used instead of version_base/version_type"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
                "version_number": "2.5.3.10",
            }
        )

        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )
        responses.add(
            "POST",
            f"{self.devhub_base_url}/tooling/sobjects/Package2/",
            json={"id": "0Ho6g000000fy4ZCAQ"},
        )
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        package_id = task._get_or_create_package(task.package_config)
        builder = BasePackageZipBuilder()

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as _, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                # Verify version_number was used instead of version_base/version_type
                assert descriptor["versionNumber"] == "2.5.3.10"
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                package_id, task.package_config, builder, skip_validation=True
            )
            # Verify version_number was parsed correctly
            assert task.options["version_number"] is not None
            assert task.options["version_number"].format() == "2.5.3.10"

    @responses.activate
    def test_dependencies_option(self, get_task, devhub_config):
        """Test that explicit dependencies option is used"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
                "dependencies": "04t000000000001,04t000000000002",
            }
        )

        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )
        responses.add(
            "POST",
            f"{self.devhub_base_url}/tooling/sobjects/Package2/",
            json={"id": "0Ho6g000000fy4ZCAQ"},
        )
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        package_id = task._get_or_create_package(task.package_config)
        builder = BasePackageZipBuilder()

        with mock.patch.object(
            task, "_get_dependencies"
        ) as mock_get_deps, mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                # Verify dependencies were set correctly
                assert "dependencies" in descriptor
                assert descriptor["dependencies"] == [
                    {"subscriberPackageVersionId": "04t000000000001"},
                    {"subscriberPackageVersionId": "04t000000000002"},
                ]
                # _get_dependencies should not be called when dependencies option is set
                mock_get_deps.assert_not_called()
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                package_id,
                task.package_config,
                builder,
                skip_validation=False,
            )
            # Verify dependencies were parsed correctly
            assert task.options["dependencies"] == [
                {"subscriberPackageVersionId": "04t000000000001"},
                {"subscriberPackageVersionId": "04t000000000002"},
            ]

    @responses.activate
    def test_apex_test_access_string_format(self, get_task, devhub_config):
        """Test apex_test_access with string format for permission sets"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.apex_test_access = {
            "permission_set_names": "PermSet1, PermSet2",
            "permission_set_license_names": "License1, License2",
        }

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                assert "permissionSetNames" in descriptor
                assert descriptor["permissionSetNames"] == ["PermSet1", "PermSet2"]
                assert "permissionSetLicenseDeveloperNames" in descriptor
                assert descriptor["permissionSetLicenseDeveloperNames"] == [
                    "License1",
                    "License2",
                ]
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )

    @responses.activate
    def test_apex_test_access_list_format(self, get_task, devhub_config):
        """Test apex_test_access with list format for permission sets"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.apex_test_access = {
            "permission_set_names": ["PermSet1", "PermSet2"],
            "permission_set_license_names": ["License1", "License2"],
        }

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                assert "permissionSetNames" in descriptor
                assert descriptor["permissionSetNames"] == ["PermSet1", "PermSet2"]
                assert "permissionSetLicenseDeveloperNames" in descriptor
                assert descriptor["permissionSetLicenseDeveloperNames"] == [
                    "License1",
                    "License2",
                ]
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )

    @responses.activate
    def test_package_metadata_access_string_format(self, get_task, devhub_config):
        """Test package_metadata_access with string format"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.package_metadata_access = {
            "permission_set_names": "MetaPermSet1, MetaPermSet2",
            "permission_set_license_names": "MetaLicense1, MetaLicense2",
        }

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                assert "packageMetadataPermissionSetNames" in descriptor
                assert descriptor["packageMetadataPermissionSetNames"] == [
                    "MetaPermSet1",
                    "MetaPermSet2",
                ]
                assert "packageMetadataPermissionSetLicenseNames" in descriptor
                assert descriptor["packageMetadataPermissionSetLicenseNames"] == [
                    "MetaLicense1",
                    "MetaLicense2",
                ]
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )

    @responses.activate
    def test_package_metadata_access_list_format(self, get_task, devhub_config):
        """Test package_metadata_access with list format"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.package_metadata_access = {
            "permission_set_names": ["MetaPermSet1", "MetaPermSet2"],
            "permission_set_license_names": ["MetaLicense1", "MetaLicense2"],
        }

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                assert "packageMetadataPermissionSetNames" in descriptor
                assert descriptor["packageMetadataPermissionSetNames"] == [
                    "MetaPermSet1",
                    "MetaPermSet2",
                ]
                assert "packageMetadataPermissionSetLicenseNames" in descriptor
                assert descriptor["packageMetadataPermissionSetLicenseNames"] == [
                    "MetaLicense1",
                    "MetaLicense2",
                ]
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )

    @responses.activate
    @mock.patch("cumulusci.tasks.create_package_version.consolidate_metadata")
    @mock.patch("cumulusci.tasks.create_package_version.convert_sfdx_source")
    @mock.patch("cumulusci.tasks.create_package_version.MetadataPackageZipBuilder")
    @mock.patch("cumulusci.tasks.create_package_version.clean_temp_directory")
    def test_get_unpackaged_metadata_path_string(
        self,
        mock_clean_temp,
        mock_zip_builder,
        mock_convert_sfdx,
        mock_consolidate,
        task,
    ):
        """Test _get_unpackaged_metadata_path with string path"""
        import tempfile

        temp_path = tempfile.mkdtemp()
        mock_consolidate.return_value = temp_path, 1
        mock_convert_sfdx.return_value.__enter__.return_value = temp_path

        mock_builder_instance = mock.Mock()
        mock_builder_instance.as_bytes.return_value = b"testzipbytes"
        mock_zip_builder.return_value = mock_builder_instance

        version_bytes = io.BytesIO()
        version_info = zipfile.ZipFile(version_bytes, "w", zipfile.ZIP_DEFLATED)

        result = task._get_unpackaged_metadata_path("unpackaged/pre", version_info)

        assert result == version_info
        mock_consolidate.assert_called_once_with(
            "unpackaged/pre", task.project_config.repo_root, logger=task.logger
        )
        mock_convert_sfdx.assert_called_once()
        mock_zip_builder.assert_called_once()
        mock_builder_instance.as_bytes.assert_called_once()
        mock_clean_temp.assert_called_once_with(temp_path)
        assert "unpackaged-metadata-package.zip" in [
            name for name in version_info.namelist()
        ]

        version_info.close()

    @responses.activate
    @mock.patch("cumulusci.tasks.create_package_version.consolidate_metadata")
    @mock.patch("cumulusci.tasks.create_package_version.convert_sfdx_source")
    @mock.patch("cumulusci.tasks.create_package_version.MetadataPackageZipBuilder")
    @mock.patch("cumulusci.tasks.create_package_version.clean_temp_directory")
    def test_get_unpackaged_metadata_path_list(
        self,
        mock_clean_temp,
        mock_zip_builder,
        mock_convert_sfdx,
        mock_consolidate,
        task,
    ):
        """Test _get_unpackaged_metadata_path with list of paths"""
        import tempfile

        temp_path = tempfile.mkdtemp()
        mock_consolidate.return_value = temp_path, 1
        mock_convert_sfdx.return_value.__enter__.return_value = temp_path

        mock_builder_instance = mock.Mock()
        mock_builder_instance.as_bytes.return_value = b"testzipbytes"
        mock_zip_builder.return_value = mock_builder_instance

        version_bytes = io.BytesIO()
        version_info = zipfile.ZipFile(version_bytes, "w", zipfile.ZIP_DEFLATED)

        metadata_paths = ["unpackaged/pre", "unpackaged/post"]
        result = task._get_unpackaged_metadata_path(metadata_paths, version_info)

        assert result == version_info
        mock_consolidate.assert_called_once_with(
            metadata_paths, task.project_config.repo_root, logger=task.logger
        )
        version_info.close()

    @responses.activate
    @mock.patch("cumulusci.tasks.create_package_version.consolidate_metadata")
    @mock.patch("cumulusci.tasks.create_package_version.convert_sfdx_source")
    @mock.patch("cumulusci.tasks.create_package_version.MetadataPackageZipBuilder")
    @mock.patch("cumulusci.tasks.create_package_version.clean_temp_directory")
    def test_get_unpackaged_metadata_path_dict(
        self,
        mock_clean_temp,
        mock_zip_builder,
        mock_convert_sfdx,
        mock_consolidate,
        task,
    ):
        """Test _get_unpackaged_metadata_path with dict format"""
        import tempfile

        temp_path = tempfile.mkdtemp()
        mock_consolidate.return_value = temp_path, 1
        mock_convert_sfdx.return_value.__enter__.return_value = temp_path

        mock_builder_instance = mock.Mock()
        mock_builder_instance.as_bytes.return_value = b"testzipbytes"
        mock_zip_builder.return_value = mock_builder_instance

        version_bytes = io.BytesIO()
        version_info = zipfile.ZipFile(version_bytes, "w", zipfile.ZIP_DEFLATED)

        metadata_paths = {"unpackaged/pre": "*.*", "unpackaged/post": "test.xml"}
        result = task._get_unpackaged_metadata_path(metadata_paths, version_info)

        assert result == version_info
        mock_consolidate.assert_called_once_with(
            metadata_paths, task.project_config.repo_root, logger=task.logger
        )
        version_info.close()

    @responses.activate
    def test_create_version_request_with_unpackaged_metadata(
        self, get_task, devhub_config
    ):
        """Test _create_version_request includes unpackaged metadata when configured"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.unpackaged_metadata_path = "unpackaged/pre"

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_unpackaged_metadata_path"
        ) as mock_unpackaged, mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            version_bytes = io.BytesIO()
            version_info = zipfile.ZipFile(version_bytes, "w", zipfile.ZIP_DEFLATED)
            mock_unpackaged.return_value = version_info

            mock_tooling_obj = mock.Mock()
            mock_tooling_obj.create.return_value = {"id": "08c000000000002AAA"}
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )

            mock_unpackaged.assert_called_once_with("unpackaged/pre", mock.ANY)
            version_info.close()

    @responses.activate
    def test_apex_test_access_partial_config(self, get_task, devhub_config):
        """Test apex_test_access with only permission_set_names"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.apex_test_access = {
            "permission_set_names": ["PermSet1"],
        }

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                assert "permissionSetNames" in descriptor
                assert "permissionSetLicenseDeveloperNames" not in descriptor
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )

    @responses.activate
    def test_package_metadata_access_partial_config(self, get_task, devhub_config):
        """Test package_metadata_access with only permission_set_license_names"""
        task = get_task(
            {
                "package_type": "Managed",
                "package_name": "Test Package",
            }
        )
        task.package_config.package_metadata_access = {
            "permission_set_license_names": ["MetaLicense1"],
        }

        builder = BasePackageZipBuilder()

        # Mock the query for existing Package2VersionCreateRequest
        responses.add(
            "GET",
            f"{self.devhub_base_url}/tooling/query/",
            json={"size": 0, "records": []},
        )

        with mock.patch.object(
            task, "_get_base_version_number"
        ) as mock_version, mock.patch.object(
            builder, "as_hash", return_value="testhash"
        ), mock.patch.object(
            builder, "as_bytes", return_value=b"testbytes"
        ), mock.patch.object(
            task, "_get_tooling_object"
        ) as mock_tooling:
            mock_version.return_value.increment.return_value.format.return_value = (
                "1.0.0.1"
            )
            mock_tooling_obj = mock.Mock()

            def capture_create(request):
                import base64

                version_info_b64 = request["VersionInfo"]
                version_info_bytes = base64.b64decode(version_info_b64)
                version_info_zip = zipfile.ZipFile(io.BytesIO(version_info_bytes), "r")
                descriptor_json = version_info_zip.read("package2-descriptor.json")
                descriptor = json.loads(descriptor_json.decode("utf-8"))
                assert "packageMetadataPermissionSetLicenseNames" in descriptor
                assert "packageMetadataPermissionSetNames" not in descriptor
                return {"id": "08c000000000002AAA"}

            mock_tooling_obj.create.side_effect = capture_create
            mock_tooling.return_value = mock_tooling_obj

            task._create_version_request(
                "0Ho6g000000fy4ZCAQ",
                task.package_config,
                builder,
                skip_validation=True,
            )
