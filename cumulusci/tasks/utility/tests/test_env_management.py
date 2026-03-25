import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from cumulusci.core.config import TaskConfig
from cumulusci.tasks.utility.env_management import (
    EnvManagement,
    EnvManagementOption,
    VcsRemoteBranch,
)
from cumulusci.tests.util import create_project_config


class TestVcsRemoteBranch(unittest.TestCase):
    def test_run_task_branch_exists(self):
        project_config = create_project_config()
        project_config.repo_info["branch"] = "feature/branch-1"
        task_config = TaskConfig(
            {
                "options": {
                    "url": "https://github.com/TestOwner/TestRepo",
                    "name": "VCS_URL",
                }
            }
        )

        with patch(
            "cumulusci.tasks.utility.env_management.get_repo_from_url"
        ) as get_repo_mock, patch.object(
            VcsRemoteBranch, "get_release_branch"
        ) as get_release_branch_mock:
            repo_mock = Mock()
            branch_mock = Mock()
            branch_mock.name = "feature/branch-1"
            get_repo_mock.return_value = repo_mock
            get_release_branch_mock.return_value = branch_mock

            task = VcsRemoteBranch(project_config, task_config)
            task()
            self.assertEqual(
                task.return_values["url"], "https://github.com/TestOwner/TestRepo"
            )
            self.assertEqual(task.return_values["branch"], "feature/branch-1")
            get_release_branch_mock.assert_called_once_with(
                repo_mock, "feature/branch-1"
            )

    def test_run_task_branch_not_exist(self):
        project_config = create_project_config()
        project_config.repo_info["branch"] = "feature/branch-1"
        task_config = TaskConfig(
            {
                "options": {
                    "url": "https://github.com/TestOwner/TestRepo",
                    "name": "VCS_URL",
                }
            }
        )

        with patch(
            "cumulusci.tasks.utility.env_management.get_repo_from_url"
        ) as get_repo_mock, patch.object(
            VcsRemoteBranch, "get_release_branch"
        ) as get_release_branch_mock:
            repo_mock = Mock()
            repo_mock.default_branch = "main"
            get_repo_mock.return_value = repo_mock
            get_release_branch_mock.side_effect = Exception("Branch not found")

            task = VcsRemoteBranch(project_config, task_config)
            task()
            self.assertEqual(
                task.return_values["url"], "https://github.com/TestOwner/TestRepo"
            )
            self.assertEqual(task.return_values["branch"], "main")
            get_release_branch_mock.assert_called_once_with(
                repo_mock, "feature/branch-1"
            )

    @patch("cumulusci.tasks.utility.env_management.parse_format_config")
    @patch("cumulusci.tasks.utility.env_management.get_release_identifier")
    @patch("cumulusci.tasks.utility.env_management.construct_release_branch_name")
    @patch("cumulusci.tasks.utility.env_management.is_release_branch_or_child")
    def test_get_release_branch_release_branch_uses_matching_remote_branch(
        self,
        is_release_branch_or_child,
        construct_release_branch_name,
        get_release_identifier,
        parse_format_config,
    ):
        project_config = create_project_config()
        project_config.repo_info["branch"] = "feature/branch-1"
        task_config = TaskConfig(
            {
                "options": {
                    "url": "https://github.com/TestOwner/TestRepo",
                    "name": "VCS_URL",
                }
            }
        )
        parse_format_config.return_value = {"prefix_release": "release"}
        is_release_branch_or_child.return_value = True
        get_release_identifier.return_value = "1.2"
        construct_release_branch_name.return_value = "feature/release/1.2"
        repo_mock = Mock()
        branch_mock = Mock()
        repo_mock.branch.return_value = branch_mock

        task = VcsRemoteBranch(project_config, task_config)
        result = task.get_release_branch(repo_mock, "feature/branch-1")
        self.assertEqual(result, branch_mock)
        repo_mock.branch.assert_called_once_with("feature/release/1.2")

    @patch("cumulusci.tasks.utility.env_management.parse_format_config")
    @patch("cumulusci.tasks.utility.env_management.get_release_identifier")
    @patch("cumulusci.tasks.utility.env_management.construct_release_branch_name")
    @patch("cumulusci.tasks.utility.env_management.is_release_branch_or_child")
    def test_get_release_branch_falls_back_to_local_branch_when_release_lookup_fails(
        self,
        is_release_branch_or_child,
        construct_release_branch_name,
        get_release_identifier,
        parse_format_config,
    ):
        project_config = create_project_config()
        project_config.repo_info["branch"] = "feature/branch-1"
        task_config = TaskConfig(
            {
                "options": {
                    "url": "https://github.com/TestOwner/TestRepo",
                    "name": "VCS_URL",
                }
            }
        )
        parse_format_config.return_value = {"prefix_release": "release"}
        is_release_branch_or_child.return_value = True
        get_release_identifier.return_value = "1.2"
        construct_release_branch_name.return_value = "feature/release/1.2"
        repo_mock = Mock()
        local_branch_mock = Mock()
        repo_mock.branch.side_effect = [Exception("release missing"), local_branch_mock]

        task = VcsRemoteBranch(project_config, task_config)
        result = task.get_release_branch(repo_mock, "feature/branch-1")
        self.assertEqual(result, local_branch_mock)
        self.assertEqual(
            repo_mock.branch.call_args_list[0].args[0], "feature/release/1.2"
        )
        self.assertEqual(repo_mock.branch.call_args_list[1].args[0], "feature/branch-1")


class TestEnvManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_config = create_project_config()
        cls.org_config = Mock()

    def test_init_options(self):
        task_config = TaskConfig(
            {
                "options": {
                    "envs": [
                        {"name": "MY_VAR", "default": "default_val"},
                        {"name": "MY_BOOL", "datatype": "bool", "default": "true"},
                    ]
                }
            }
        )
        task = EnvManagement(self.project_config, task_config)
        self.assertEqual(len(task.parsed_options.envs), 2)
        self.assertIsInstance(task.parsed_options.envs[0], EnvManagementOption)

    @patch.dict(os.environ, {}, clear=True)
    def test_run_task_get_values(self):
        os.environ["MY_VAR"] = "env_val"
        os.environ["MY_INT"] = "123"
        os.environ["MY_DATE"] = "2023-10-26"
        os.environ["MY_LIST"] = "a,b,c"

        task_config = TaskConfig(
            {
                "options": {
                    "envs": [
                        {"name": "MY_VAR"},
                        {"name": "MY_INT", "datatype": "int"},
                        {"name": "MY_DATE", "datatype": "date"},
                        {"name": "MY_LIST", "datatype": "list"},
                        {"name": "NOT_SET", "default": "default_val"},
                    ]
                }
            }
        )
        task = EnvManagement(self.project_config, task_config, self.org_config)
        result = task()

        self.assertEqual(
            result,
            {
                "MY_VAR": "env_val",
                "MY_INT": 123,
                "MY_DATE": date(2023, 10, 26),
                "MY_LIST": ["a", "b", "c"],
                "NOT_SET": "default_val",
            },
        )
        self.assertNotIn("NOT_SET", os.environ)

    @patch.dict(os.environ, {}, clear=True)
    def test_run_task_set_values(self):
        os.environ["EXISTING_VAR"] = "original_value"
        task_config = TaskConfig(
            {
                "options": {
                    "envs": [
                        {"name": "NEW_VAR", "default": "new_value", "set": True},
                        {
                            "name": "EXISTING_VAR",
                            "default": "new_default",
                            "set": True,
                        },
                    ]
                }
            }
        )
        task = EnvManagement(self.project_config, task_config, self.org_config)
        task()

        self.assertEqual(os.environ.get("NEW_VAR"), "new_value")
        self.assertEqual(os.environ.get("EXISTING_VAR"), "original_value")

    def test_datatype_validation(self):
        with self.assertRaises(ValueError):
            EnvManagementOption(name="test", datatype="invalid")

    @patch.dict(os.environ, {}, clear=True)
    def _test_datatype_conversion(self, datatype, env_value, expected_value):
        os.environ["TEST_VAR"] = str(env_value)
        task_config = TaskConfig(
            {"options": {"envs": [{"name": "TEST_VAR", "datatype": datatype}]}}
        )
        task = EnvManagement(self.project_config, task_config, self.org_config)
        result = task()
        self.assertEqual(result["TEST_VAR"], expected_value)

    def test_datatypes(self):
        test_cases = [
            ("string", "hello", "hello"),
            ("bool", "true", True),
            ("bool", "0", False),
            ("int", "42", 42),
            ("float", "3.14", 3.14),
            ("date", "2024-01-01", date(2024, 1, 1)),
            ("list", "one,two", ["one", "two"]),
            ("dict", '{"key": "value"}', {"key": "value"}),
            ("path", "/tmp/test", Path("/tmp/test").absolute()),
            ("directory", "/tmp/test/file.txt", Path("/tmp/test").absolute()),
            ("filename", "/tmp/test/file.txt", "file.txt"),
        ]
        for datatype, env_value, expected_value in test_cases:
            with self.subTest(datatype=datatype):
                self._test_datatype_conversion(datatype, env_value, expected_value)

    def test_formatting_error(self):
        os.environ["TEST_VAR"] = "not-an-int"
        task_config = TaskConfig(
            {"options": {"envs": [{"name": "TEST_VAR", "datatype": "int"}]}}
        )
        task = EnvManagement(self.project_config, task_config, self.org_config)
        with self.assertRaises(ValueError):
            task()

    @patch("cumulusci.tasks.utility.env_management.VcsRemoteBranch")
    def test_vcs_repo_datatype(self, vcs_mock):
        vcs_instance_mock = vcs_mock.return_value
        vcs_instance_mock.return_value = {
            "url": "https://github.com/TestOwner/TestRepo",
            "branch": "my-feature-branch",
        }

        task_config = TaskConfig(
            {
                "options": {
                    "envs": [
                        {
                            "name": "VCS_URL",
                            "datatype": "vcs_repo",
                            "default": "https://github.com/TestOwner/TestRepo",
                        }
                    ]
                }
            }
        )
        task = EnvManagement(self.project_config, task_config, self.org_config)
        result = task()

        self.assertEqual(result["VCS_URL"], "https://github.com/TestOwner/TestRepo")
        self.assertEqual(result["VCS_URL_BRANCH"], "my-feature-branch")
        vcs_mock.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_run_task_with_default_types(self):
        task_config = TaskConfig(
            {
                "options": {
                    "envs": [
                        {"name": "MY_LIST", "datatype": "list", "default": ["a", "b"]},
                        {"name": "MY_DICT", "datatype": "dict", "default": {"x": 1}},
                    ]
                }
            }
        )
        task = EnvManagement(self.project_config, task_config, self.org_config)
        result = task()
        self.assertEqual(result["MY_LIST"], ["a", "b"])
        self.assertEqual(result["MY_DICT"], {"x": 1})
