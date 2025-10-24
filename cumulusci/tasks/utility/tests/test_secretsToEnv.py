"""Tests for secretsToEnv module."""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from cumulusci.core.config import TaskConfig
from cumulusci.tasks.utility.credentialManager import DevEnvironmentVariableProvider
from cumulusci.tasks.utility.secretsToEnv import SecretsToEnv


class TestSecretsToEnvOptions:
    """Test cases for SecretsToEnv options configuration."""

    def test_default_options(self):
        """Test initialization with default options."""
        task_config = TaskConfig({"options": {}})
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")
            task_config.options["env_path"] = env_path

            task = SecretsToEnv(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert task.parsed_options.env_path == Path(env_path)
            assert task.parsed_options.secrets_provider is None
            assert task.parsed_options.provider_options == {}
            assert task.parsed_options.secrets == []

    def test_custom_options(self):
        """Test initialization with custom options."""
        task_config = TaskConfig(
            {
                "options": {
                    "env_path": ".custom.env",
                    "secrets_provider": "environment",
                    "provider_options": {"key_prefix": "CUSTOM_"},
                    "secrets": ["API_KEY", "DB_PASSWORD"],
                }
            }
        )

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        assert task.parsed_options.env_path == Path(".custom.env")
        assert task.parsed_options.secrets_provider == "environment"
        assert task.parsed_options.provider_options == {"key_prefix": "CUSTOM_"}
        assert task.parsed_options.secrets == ["API_KEY", "DB_PASSWORD"]

    def test_secrets_as_mapping(self):
        """Test initialization with secrets as mapping."""
        task_config = TaskConfig(
            {
                "options": {
                    "env_path": ".env",
                    "secrets": {"DB_URL": "database_url", "API_KEY": "api_key"},
                }
            }
        )

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        assert task.parsed_options.secrets == {
            "DB_URL": "database_url",
            "API_KEY": "api_key",
        }


class TestSecretsToEnvInitialization:
    """Test cases for SecretsToEnv initialization methods."""

    def test_init_options_creates_provider(self):
        """Test that _init_options creates the correct provider."""
        task_config = TaskConfig(
            {
                "options": {
                    "env_path": ".env",
                    "secrets_provider": "local",
                }
            }
        )

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        assert task.provider is not None
        assert isinstance(task.provider, DevEnvironmentVariableProvider)

    def test_init_options_loads_existing_env_file(self):
        """Test that _init_options loads existing .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            # Create existing .env file
            with open(env_path, "w") as f:
                f.write('EXISTING_KEY="existing_value"\n')

            task_config = TaskConfig({"options": {"env_path": env_path}})

            task = SecretsToEnv(
                project_config=mock.Mock(),
                task_config=task_config,
                org_config=None,
            )

            assert "EXISTING_KEY" in task.env_values
            assert task.env_values["EXISTING_KEY"] == "existing_value"

    def test_init_secrets_with_list_of_strings(self):
        """Test _init_secrets with list of strings."""
        task_config = TaskConfig(
            {
                "options": {
                    "env_path": ".env",
                    "secrets": ["API_KEY", "DB_PASSWORD", "TOKEN"],
                }
            }
        )

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        task._init_secrets()

        # Should convert list to mapping with same key and value
        assert task.secrets == {
            "API_KEY": "API_KEY",
            "DB_PASSWORD": "DB_PASSWORD",
            "TOKEN": "TOKEN",
        }

    def test_init_secrets_with_mapping_format_in_list(self):
        """Test _init_secrets with mapping format in list (key:value)."""
        task_config = TaskConfig(
            {
                "options": {
                    "env_path": ".env",
                    "secrets": ["DB_URL:database_url", "API_KEY:api_key"],
                }
            }
        )

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        task._init_secrets()

        # Should parse as mapping
        assert task.secrets == {
            "DB_URL": "database_url",
            "API_KEY": "api_key",
        }

    def test_init_secrets_with_empty_list(self):
        """Test _init_secrets with empty list doesn't initialize secrets."""
        task_config = TaskConfig(
            {
                "options": {
                    "env_path": ".env",
                    "secrets": [],
                }
            }
        )

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        task._init_secrets()

        # Should not set secrets attribute if list is empty
        assert task.secrets == {}


class TestSecretsToEnvGetCredential:
    """Test cases for _get_credential method."""

    def test_get_credential_success(self):
        """Test _get_credential successfully retrieves credential."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = "secret_value_123"
        task.provider = mock_provider

        safe_value, original_value = task._get_credential(
            "API_KEY", "api_key", secret_name="my-secret"
        )

        assert safe_value == "secret_value_123"
        assert original_value == "secret_value_123"
        mock_provider.get_credentials.assert_called_once_with(
            "API_KEY", {"value": "api_key", "secret_name": "my-secret"}
        )

    def test_get_credential_escapes_quotes(self):
        """Test _get_credential escapes double quotes."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = 'value_with_"quotes"'
        task.provider = mock_provider

        safe_value, _ = task._get_credential("API_KEY", "api_key")

        assert safe_value == 'value_with_\\"quotes\\"'

    def test_get_credential_escapes_newlines(self):
        """Test _get_credential escapes newlines."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = "line1\nline2\nline3"
        task.provider = mock_provider

        safe_value, _ = task._get_credential("API_KEY", "api_key")

        assert safe_value == "line1\\nline2\\nline3"

    def test_get_credential_handles_both_quotes_and_newlines(self):
        """Test _get_credential handles both quotes and newlines."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = 'line1 "quoted"\nline2'
        task.provider = mock_provider

        safe_value, _ = task._get_credential("API_KEY", "api_key")

        assert safe_value == 'line1 \\"quoted\\"\\nline2'

    def test_get_credential_with_none_value_raises_error(self):
        """Test _get_credential raises error when provider returns None."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = None
        task.provider = mock_provider

        with pytest.raises(ValueError) as exc_info:
            task._get_credential("API_KEY", "api_key")

        assert "Failed to retrieve secret API_KEY from local" in str(exc_info.value)

    def test_get_credential_uses_env_key_parameter(self):
        """Test _get_credential uses custom env_key when provided."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = "secret_value"
        task.provider = mock_provider

        safe_value, _ = task._get_credential(
            "CREDENTIAL_KEY", "value", env_key="CUSTOM_ENV_KEY"
        )

        assert safe_value == "secret_value"

    def test_get_credential_logs_masked_value(self, caplog):
        """Test _get_credential logs masked value."""
        import logging

        caplog.set_level(logging.INFO)
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "local"
        mock_provider.get_credentials.return_value = "secret_value"
        task.provider = mock_provider

        task._get_credential("API_KEY", "api_key")

        # Check that the log contains masked value
        assert "API_KEY=*****" in caplog.text


class TestSecretsToEnvGetAllCredentials:
    """Test cases for _get_all_credentials method."""

    def test_get_all_credentials_success(self):
        """Test _get_all_credentials successfully retrieves all credentials."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "aws_secrets"
        mock_provider.get_all_credentials.return_value = {
            "API_KEY": "api_value",
            "DB_PASSWORD": "db_pass",
            "TOKEN": "token_value",
        }
        task.provider = mock_provider

        result = task._get_all_credentials("*", secret_name="my-app/secrets")

        assert result == {
            "API_KEY": "api_value",
            "DB_PASSWORD": "db_pass",
            "TOKEN": "token_value",
        }
        mock_provider.get_all_credentials.assert_called_once_with(
            "*", {"secret_name": "my-app/secrets"}
        )

    def test_get_all_credentials_escapes_quotes(self):
        """Test _get_all_credentials escapes quotes in all values."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "aws_secrets"
        mock_provider.get_all_credentials.return_value = {
            "KEY1": 'value_with_"quotes"',
            "KEY2": "normal_value",
        }
        task.provider = mock_provider

        result = task._get_all_credentials("*")

        assert result["KEY1"] == 'value_with_\\"quotes\\"'
        assert result["KEY2"] == "normal_value"

    def test_get_all_credentials_escapes_newlines(self):
        """Test _get_all_credentials escapes newlines in all values."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "aws_secrets"
        mock_provider.get_all_credentials.return_value = {
            "KEY1": "line1\nline2",
            "KEY2": "single_line",
        }
        task.provider = mock_provider

        result = task._get_all_credentials("*")

        assert result["KEY1"] == "line1\\nline2"
        assert result["KEY2"] == "single_line"

    def test_get_all_credentials_with_none_value_raises_error(self):
        """Test _get_all_credentials raises error when provider returns None."""
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "aws_secrets"
        mock_provider.get_all_credentials.return_value = None
        task.provider = mock_provider

        with pytest.raises(ValueError) as exc_info:
            task._get_all_credentials("*", secret_name="my-secret")

        assert "Failed to retrieve secret *(my-secret) from aws_secrets" in str(
            exc_info.value
        )

    def test_get_all_credentials_logs_masked_values(self, caplog):
        """Test _get_all_credentials logs masked values for all keys."""
        import logging

        caplog.set_level(logging.INFO)
        task_config = TaskConfig({"options": {"env_path": ".env"}})

        task = SecretsToEnv(
            project_config=mock.Mock(),
            task_config=task_config,
            org_config=None,
        )

        mock_provider = mock.Mock()
        mock_provider.provider_type = "aws_secrets"
        mock_provider.get_all_credentials.return_value = {
            "API_KEY": "api_value",
            "DB_PASSWORD": "db_pass",
        }
        task.provider = mock_provider

        task._get_all_credentials("*")

        # Check that logs contain masked values
        assert "API_KEY=*****" in caplog.text
        assert "DB_PASSWORD=*****" in caplog.text


class TestSecretsToEnvRunTask:
    """Test cases for _run_task method."""

    def test_run_task_with_simple_secrets(self):
        """Test _run_task with simple list of secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["API_KEY", "DB_PASSWORD"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.side_effect = [
                "api_secret_123",
                "db_pass_456",
            ]
            task.provider = mock_provider

            task()

            # Verify file was created
            assert os.path.exists(env_path)

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'API_KEY="api_secret_123"' in content
            assert 'DB_PASSWORD="db_pass_456"' in content

    def test_run_task_with_wildcard_secret(self):
        """Test _run_task with wildcard to get all secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": {"*": "my-app/secrets"},
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # When secrets is a dict, _init_secrets doesn't set task.secrets
            # so we need to set it manually for this test
            task.secrets = task.parsed_options.secrets

            mock_provider = mock.Mock()
            mock_provider.provider_type = "aws_secrets"
            mock_provider.get_all_credentials.return_value = {
                "API_KEY": "api_value",
                "DB_PASSWORD": "db_pass",
                "TOKEN": "token_value",
            }
            task.provider = mock_provider

            task()

            # Verify file was created
            assert os.path.exists(env_path)

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'API_KEY="api_value"' in content
            assert 'DB_PASSWORD="db_pass"' in content
            assert 'TOKEN="token_value"' in content

    def test_run_task_creates_directory_if_not_exists(self):
        """Test _run_task creates parent directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, "subdir", "nested", ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["API_KEY"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.return_value = "api_secret"
            task.provider = mock_provider

            task()

            # Verify directory and file were created
            assert os.path.exists(os.path.dirname(env_path))
            assert os.path.exists(env_path)

    def test_run_task_preserves_existing_env_values(self):
        """Test _run_task preserves existing environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            # Create existing .env file
            with open(env_path, "w") as f:
                f.write('EXISTING_KEY="existing_value"\n')
                f.write('ANOTHER_KEY="another_value"\n')

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["NEW_SECRET"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.return_value = "new_secret_value"
            task.provider = mock_provider

            task()

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'EXISTING_KEY="existing_value"' in content
            assert 'ANOTHER_KEY="another_value"' in content
            assert 'NEW_SECRET="new_secret_value"' in content

    def test_run_task_overwrites_duplicate_keys(self):
        """Test _run_task overwrites duplicate keys with new values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            # Create existing .env file with key to be overwritten
            with open(env_path, "w") as f:
                f.write('API_KEY="old_value"\n')

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["API_KEY"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.return_value = "new_value"
            task.provider = mock_provider

            task()

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'API_KEY="new_value"' in content
            assert 'API_KEY="old_value"' not in content

    def test_run_task_with_mixed_secrets_and_wildcard(self):
        """Test _run_task with combination of specific secrets and wildcard."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": {
                            "*": "my-app/secrets",
                            "SPECIFIC_KEY": "specific_value",
                        },
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # When secrets is a dict, _init_secrets doesn't set task.secrets
            # so we need to set it manually for this test
            task.secrets = task.parsed_options.secrets

            mock_provider = mock.Mock()
            mock_provider.provider_type = "aws_secrets"

            def get_credentials_side_effect(key, options):
                if key == "SPECIFIC_KEY":
                    return "specific_secret"
                return None

            mock_provider.get_credentials.side_effect = get_credentials_side_effect
            mock_provider.get_all_credentials.return_value = {
                "WILDCARD_KEY1": "wildcard_value1",
                "WILDCARD_KEY2": "wildcard_value2",
            }
            task.provider = mock_provider

            task()

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'WILDCARD_KEY1="wildcard_value1"' in content
            assert 'WILDCARD_KEY2="wildcard_value2"' in content
            assert 'SPECIFIC_KEY="specific_secret"' in content

    def test_run_task_creates_env_in_current_directory(self):
        """Test _run_task creates .env in current directory when dirname is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = ".env"  # No directory component

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["API_KEY"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.return_value = "api_secret"
            task.provider = mock_provider

            task()

            # Verify file was created in current directory
            full_path = os.path.join(tmpdir, env_path)
            assert os.path.exists(full_path)


class TestSecretsToEnvIntegration:
    """Integration tests for SecretsToEnv with different providers."""

    @mock.patch.dict(os.environ, {"TEST_API_KEY": "env_api_secret"})
    def test_integration_with_environment_provider(self):
        """Test full workflow with environment provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets_provider": "environment",
                        "provider_options": {"key_prefix": "TEST_"},
                        "secrets": ["API_KEY"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            task()

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'API_KEY="env_api_secret"' in content

    def test_integration_with_local_provider(self):
        """Test full workflow with local provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets_provider": "local",
                        "secrets": ["API_KEY", "DB_PASS"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            task()

            # Verify file contents
            # Local provider returns the key itself as the value
            with open(env_path, "r") as f:
                content = f.read()

            assert 'API_KEY="API_KEY"' in content
            assert 'DB_PASS="DB_PASS"' in content

    def test_integration_with_aws_provider(self):
        """Test full workflow with AWS Secrets Manager provider."""
        import json
        import sys

        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        secret_data = {"API_KEY": "aws_api_value", "DB_PASSWORD": "aws_db_pass"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets_provider": "aws_secrets",
                        "provider_options": {"aws_region": "us-east-1"},
                        "secrets": {"*": "my-app/secrets"},
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            with mock.patch.dict(
                sys.modules, {"boto3": mock_boto3, "botocore.exceptions": mock.Mock()}
            ):
                task = SecretsToEnv(
                    project_config=project_config,
                    task_config=task_config,
                    org_config=None,
                )

                # When secrets is a dict, _init_secrets doesn't set task.secrets
                # so we need to set it manually for this test
                task.secrets = task.parsed_options.secrets

                task()

                # Verify file contents
                with open(env_path, "r") as f:
                    content = f.read()

                assert 'API_KEY="aws_api_value"' in content
                assert 'DB_PASSWORD="aws_db_pass"' in content

    @mock.patch.dict(os.environ, {"MYAPP_API_TOKEN": "ado_token_value"})
    def test_integration_with_ado_provider(self):
        """Test full workflow with Azure DevOps variables provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets_provider": "ado_variables",
                        "provider_options": {"key_prefix": "MYAPP_"},
                        "secrets": ["API_TOKEN"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            task()

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert 'API_TOKEN="ado_token_value"' in content


class TestSecretsToEnvEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_secrets_list_creates_empty_env_file(self):
        """Test that empty secrets list still creates/updates env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            # Create existing .env file
            with open(env_path, "w") as f:
                f.write('EXISTING="value"\n')

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": [],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            # When secrets is an empty list, _init_secrets doesn't set task.secrets
            # so we need to set it manually for this test
            task.secrets = {}

            task()

            # Verify existing content is preserved
            with open(env_path, "r") as f:
                content = f.read()

            assert 'EXISTING="value"' in content

    def test_special_characters_in_secret_values(self):
        """Test handling of special characters in secret values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["SPECIAL"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.return_value = (
                "value!@#$%^&*()[]{}|\\;':<>?,./~`"
            )
            task.provider = mock_provider

            task()

            # Verify file can be read
            assert os.path.exists(env_path)

    def test_unicode_characters_in_secret_values(self):
        """Test handling of unicode characters in secret values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["UNICODE"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            mock_provider.get_credentials.return_value = "Hello 世界 🌍 Привет"
            task.provider = mock_provider

            task()

            # Verify file contents
            with open(env_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert 'UNICODE="Hello 世界 🌍 Привет"' in content

    def test_very_long_secret_value(self):
        """Test handling of very long secret values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, ".env")

            task_config = TaskConfig(
                {
                    "options": {
                        "env_path": env_path,
                        "secrets": ["LONG_SECRET"],
                    }
                }
            )

            project_config = mock.Mock()
            project_config.repo_root = tmpdir

            task = SecretsToEnv(
                project_config=project_config,
                task_config=task_config,
                org_config=None,
            )

            mock_provider = mock.Mock()
            mock_provider.provider_type = "local"
            long_value = "x" * 10000  # 10k characters
            mock_provider.get_credentials.return_value = long_value
            task.provider = mock_provider

            task()

            # Verify file contents
            with open(env_path, "r") as f:
                content = f.read()

            assert f'LONG_SECRET="{long_value}"' in content
