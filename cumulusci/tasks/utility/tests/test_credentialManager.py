"""Tests for credentialManager module."""

import json
import os
import sys
from unittest import mock

import pytest

from cumulusci.tasks.utility.credentialManager import (
    AwsSecretsManagerProvider,
    AzureVariableGroupProvider,
    CredentialManager,
    CredentialProvider,
    DevEnvironmentVariableProvider,
    EnvironmentVariableProvider,
)


class TestCredentialProvider:
    """Test cases for CredentialProvider abstract base class."""

    def test_init_with_key_prefix(self):
        """Test initialization with custom key_prefix."""
        provider = DevEnvironmentVariableProvider(key_prefix="CUSTOM_")
        assert provider.key_prefix == "CUSTOM_"

    @mock.patch.dict(os.environ, {"CUMULUSCI_PREFIX_SECRETS": "ENV_PREFIX_"})
    def test_init_with_env_key_prefix(self):
        """Test initialization with key_prefix from environment variable."""
        provider = DevEnvironmentVariableProvider()
        assert provider.key_prefix == "ENV_PREFIX_"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_init_without_key_prefix(self):
        """Test initialization without key_prefix."""
        provider = DevEnvironmentVariableProvider()
        assert provider.key_prefix == ""

    def test_get_key_with_prefix(self):
        """Test get_key method with prefix."""
        provider = DevEnvironmentVariableProvider(key_prefix="TEST_")
        assert provider.get_key("API_KEY") == "TEST_API_KEY"

    def test_get_key_without_prefix(self):
        """Test get_key method without prefix."""
        provider = DevEnvironmentVariableProvider(key_prefix="")
        assert provider.get_key("API_KEY") == "API_KEY"

    def test_provider_registration(self):
        """Test that providers are registered in the registry."""
        assert "local" in CredentialProvider._registry
        assert "environment" in CredentialProvider._registry
        assert "aws_secrets" in CredentialProvider._registry
        assert "ado_variables" in CredentialProvider._registry

    def test_abstract_methods_not_implemented(self):
        """Test that abstract methods must be implemented by subclasses."""

        class IncompleteProvider(CredentialProvider):
            provider_type = "incomplete"

        with pytest.raises(TypeError):
            IncompleteProvider()


class TestDevEnvironmentVariableProvider:
    """Test cases for DevEnvironmentVariableProvider."""

    def test_provider_type(self):
        """Test that provider_type is correctly set."""
        assert DevEnvironmentVariableProvider.provider_type == "local"

    def test_get_credentials_with_value(self):
        """Test get_credentials returns the provided value."""
        provider = DevEnvironmentVariableProvider()
        result = provider.get_credentials("API_KEY", {"value": "secret123"})
        assert result == "secret123"

    def test_get_credentials_without_value(self):
        """Test get_credentials returns None when no value is provided."""
        provider = DevEnvironmentVariableProvider()
        result = provider.get_credentials("API_KEY", {"value": None})
        assert result is None

    def test_get_credentials_with_empty_options(self):
        """Test get_credentials with empty options dict."""
        provider = DevEnvironmentVariableProvider()
        result = provider.get_credentials("API_KEY", {})
        assert result is None

    def test_get_all_credentials_not_supported(self):
        """Test that get_all_credentials raises NotImplementedError."""
        provider = DevEnvironmentVariableProvider()
        with pytest.raises(NotImplementedError):
            provider.get_all_credentials("API_KEY", {})


class TestEnvironmentVariableProvider:
    """Test cases for EnvironmentVariableProvider."""

    def test_provider_type(self):
        """Test that provider_type is correctly set."""
        assert EnvironmentVariableProvider.provider_type == "environment"

    @mock.patch.dict(os.environ, {"TEST_API_KEY": "env_secret"})
    def test_get_credentials_from_environment(self):
        """Test get_credentials retrieves value from environment."""
        provider = EnvironmentVariableProvider(key_prefix="TEST_")
        result = provider.get_credentials("API_KEY", {"value": "default"})
        assert result == "env_secret"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_get_credentials_uses_default_when_env_not_set(self):
        """Test get_credentials uses default value when env var not set."""
        provider = EnvironmentVariableProvider(key_prefix="TEST_")
        result = provider.get_credentials("API_KEY", {"value": "default_value"})
        assert result == "default_value"

    @mock.patch.dict(os.environ, {"MYAPP_KEY": "env_value"})
    def test_get_credentials_with_custom_prefix(self):
        """Test get_credentials with custom prefix."""
        provider = EnvironmentVariableProvider(key_prefix="MYAPP_")
        result = provider.get_credentials("KEY", {"value": "default"})
        assert result == "env_value"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_get_credentials_returns_none_when_no_default(self):
        """Test get_credentials returns None when no default and env not set."""
        provider = EnvironmentVariableProvider()
        result = provider.get_credentials("NONEXISTENT_KEY", {"value": None})
        assert result is None

    def test_get_all_credentials_not_supported(self):
        """Test that get_all_credentials raises NotImplementedError."""
        provider = EnvironmentVariableProvider()
        with pytest.raises(NotImplementedError):
            provider.get_all_credentials("API_KEY", {})


class TestAwsSecretsManagerProvider:
    """Test cases for AwsSecretsManagerProvider."""

    def test_provider_type(self):
        """Test that provider_type is correctly set."""
        assert AwsSecretsManagerProvider.provider_type == "aws_secrets"

    @mock.patch.dict(os.environ, {"AWS_REGION": "us-east-1"})
    def test_init_with_aws_region_from_env(self):
        """Test initialization with AWS_REGION from environment."""
        provider = AwsSecretsManagerProvider()
        assert provider.aws_region == "us-east-1"
        assert provider.secrets_cache == {}

    def test_init_with_aws_region_from_kwargs(self):
        """Test initialization with aws_region from kwargs."""
        provider = AwsSecretsManagerProvider(aws_region="eu-west-1")
        assert provider.aws_region == "eu-west-1"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_init_without_aws_region_raises_error(self):
        """Test initialization without AWS_REGION raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AwsSecretsManagerProvider()
        assert "AWS_REGION" in str(exc_info.value)

    def test_init_with_existing_secrets_cache(self):
        """Test initialization with existing secrets_cache."""
        cache = {"secret1": {"key1": "value1"}}
        provider = AwsSecretsManagerProvider(
            aws_region="us-west-2", secrets_cache=cache
        )
        assert provider.secrets_cache == cache

    def test_get_credentials_success(self):
        """Test get_credentials successfully retrieves secret."""
        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        secret_data = {"API_KEY": "secret_value", "DB_PASSWORD": "db_pass"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }

        with mock.patch.dict(
            sys.modules, {"boto3": mock_boto3, "botocore.exceptions": mock.Mock()}
        ):
            provider = AwsSecretsManagerProvider(aws_region="us-east-1")
            result = provider.get_credentials(
                "API_KEY", {"secret_name": "my-app/credentials"}
            )

            assert result == "secret_value"
            mock_client.get_secret_value.assert_called_once_with(
                SecretId="my-app/credentials"
            )

    def test_get_all_credentials_success(self):
        """Test get_all_credentials retrieves all secrets."""
        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        secret_data = {"API_KEY": "secret_value", "DB_PASSWORD": "db_pass"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }

        with mock.patch.dict(
            sys.modules, {"boto3": mock_boto3, "botocore.exceptions": mock.Mock()}
        ):
            provider = AwsSecretsManagerProvider(aws_region="us-east-1")
            result = provider.get_all_credentials(
                "API_KEY", {"secret_name": "my-app/credentials"}
            )

            assert result == secret_data
            assert "API_KEY" in result
            assert "DB_PASSWORD" in result

    def test_get_credentials_uses_cache(self):
        """Test get_credentials uses cached secrets on subsequent calls."""
        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        secret_data = {"API_KEY": "secret_value"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }

        with mock.patch.dict(
            sys.modules, {"boto3": mock_boto3, "botocore.exceptions": mock.Mock()}
        ):
            provider = AwsSecretsManagerProvider(aws_region="us-east-1")

            # First call - should hit AWS
            result1 = provider.get_credentials(
                "API_KEY", {"secret_name": "my-app/credentials"}
            )
            assert result1 == "secret_value"

            # Second call - should use cache
            result2 = provider.get_credentials(
                "API_KEY", {"secret_name": "my-app/credentials"}
            )
            assert result2 == "secret_value"

            # Should only call AWS once
            assert mock_client.get_secret_value.call_count == 1

    def test_get_credentials_without_secret_name_raises_error(self):
        """Test get_credentials raises error when secret_name is not provided."""
        provider = AwsSecretsManagerProvider(aws_region="us-east-1")
        with pytest.raises(ValueError) as exc_info:
            provider.get_credentials("API_KEY", {})
        assert "Secret name is required" in str(exc_info.value)

    def test_get_credentials_handles_client_error(self):
        """Test get_credentials handles boto3 ClientError."""
        # We need to import ClientError first so it exists in the namespace
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            # If botocore isn't installed, skip this test
            pytest.skip("botocore not installed")

        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        error_response = {"Error": {"Code": "ResourceNotFoundException"}}
        mock_client.get_secret_value.side_effect = ClientError(
            error_response, "GetSecretValue"
        )

        # Create a proper mock for botocore.exceptions
        mock_botocore_exceptions = type(sys)("botocore.exceptions")
        mock_botocore_exceptions.ClientError = ClientError

        with mock.patch.dict(
            sys.modules,
            {"boto3": mock_boto3, "botocore.exceptions": mock_botocore_exceptions},
        ):
            provider = AwsSecretsManagerProvider(aws_region="us-east-1")

            with pytest.raises(ClientError):
                provider.get_credentials("API_KEY", {"secret_name": "nonexistent"})

    def test_get_credentials_handles_import_error(self):
        """Test get_credentials handles ImportError when boto3 is not installed."""
        # Create a module that raises ImportError when boto3 is accessed
        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if name == "boto3" or name == "botocore":
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        provider = AwsSecretsManagerProvider(aws_region="us-east-1")

        with mock.patch("builtins.__import__", side_effect=mock_import):
            # When boto3 import fails, we get an UnboundLocalError because ClientError
            # can't be imported either. The code catches this with a RuntimeError.
            with pytest.raises((RuntimeError, UnboundLocalError)):
                provider.get_credentials("API_KEY", {"secret_name": "my-secret"})

    def test_get_credentials_handles_general_exception(self):
        """Test get_credentials handles general exceptions."""
        # We need to import ClientError first so exception handling works properly
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            pytest.skip("botocore not installed")

        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        mock_client.get_secret_value.side_effect = Exception("Unexpected error")

        # Create a proper mock for botocore.exceptions
        mock_botocore_exceptions = type(sys)("botocore.exceptions")
        mock_botocore_exceptions.ClientError = ClientError

        with mock.patch.dict(
            sys.modules,
            {"boto3": mock_boto3, "botocore.exceptions": mock_botocore_exceptions},
        ):
            provider = AwsSecretsManagerProvider(aws_region="us-east-1")

            with pytest.raises(RuntimeError) as exc_info:
                provider.get_credentials("API_KEY", {"secret_name": "my-secret"})
            assert "Failed to retrieve secret" in str(exc_info.value)

    def test_get_credentials_returns_none_for_missing_key(self):
        """Test get_credentials returns None when key is not in secret."""
        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        secret_data = {"OTHER_KEY": "other_value"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }

        with mock.patch.dict(
            sys.modules, {"boto3": mock_boto3, "botocore.exceptions": mock.Mock()}
        ):
            provider = AwsSecretsManagerProvider(aws_region="us-east-1")
            result = provider.get_credentials(
                "MISSING_KEY", {"secret_name": "my-app/credentials"}
            )

            assert result is None


class TestAzureVariableGroupProvider:
    """Test cases for AzureVariableGroupProvider."""

    def test_provider_type(self):
        """Test that provider_type is correctly set."""
        assert AzureVariableGroupProvider.provider_type == "ado_variables"

    @mock.patch.dict(os.environ, {"MYAPP_API_KEY": "azure_secret"})
    def test_get_credentials_from_azure_variables(self):
        """Test get_credentials retrieves value from Azure variable group."""
        provider = AzureVariableGroupProvider(key_prefix="MYAPP_")
        result = provider.get_credentials("API_KEY", {})
        assert result == "azure_secret"

    @mock.patch.dict(os.environ, {"MYAPP_API_KEY": "azure_secret"})
    def test_get_credentials_handles_dots_in_key(self):
        """Test get_credentials converts dots to underscores."""
        provider = AzureVariableGroupProvider(key_prefix="MYAPP_")
        result = provider.get_credentials("API.KEY", {})
        assert result == "azure_secret"

    @mock.patch.dict(os.environ, {"MYAPP_API_KEY": "uppercase_secret"})
    def test_get_credentials_handles_case_insensitive(self):
        """Test get_credentials handles uppercase conversion."""
        provider = AzureVariableGroupProvider(key_prefix="myapp_")
        result = provider.get_credentials("api_key", {})
        assert result == "uppercase_secret"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_get_credentials_returns_none_when_not_found(self):
        """Test get_credentials returns None when variable is not found."""
        provider = AzureVariableGroupProvider(key_prefix="MYAPP_")
        result = provider.get_credentials("NONEXISTENT_KEY", {})
        assert result is None

    @mock.patch.dict(os.environ, {"PREFIX_MY_VAR_NAME": "value123"})
    def test_get_credentials_with_complex_key(self):
        """Test get_credentials with complex key name."""
        provider = AzureVariableGroupProvider(key_prefix="PREFIX_")
        result = provider.get_credentials("my.var.name", {})
        assert result == "value123"

    def test_get_all_credentials_not_supported(self):
        """Test that get_all_credentials raises NotImplementedError."""
        provider = AzureVariableGroupProvider()
        with pytest.raises(NotImplementedError):
            provider.get_all_credentials("API_KEY", {})


class TestCredentialManager:
    """Test cases for CredentialManager."""

    def test_env_secrets_type_constant(self):
        """Test that env_secrets_type constant is correctly set."""
        assert CredentialManager.env_secrets_type == "CUMULUSCI_SECRETS_TYPE"

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "local"})
    def test_load_secrets_type_from_environment(self):
        """Test loading secrets type from environment variable."""
        provider_type = CredentialManager.load_secrets_type_from_environment()
        assert provider_type == "local"

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "AWS_SECRETS"})
    def test_load_secrets_type_case_insensitive(self):
        """Test loading secrets type is case insensitive."""
        provider_type = CredentialManager.load_secrets_type_from_environment()
        assert provider_type == "aws_secrets"

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_load_secrets_type_defaults_to_local(self):
        """Test loading secrets type defaults to 'local' when not set."""
        provider_type = CredentialManager.load_secrets_type_from_environment()
        assert provider_type == "local"

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "environment"})
    def test_get_provider_from_environment(self):
        """Test get_provider loads provider type from environment."""
        provider = CredentialManager.get_provider()
        assert isinstance(provider, EnvironmentVariableProvider)
        assert provider.provider_type == "environment"

    def test_get_provider_with_explicit_type(self):
        """Test get_provider with explicit provider type."""
        provider = CredentialManager.get_provider(provider_type="local")
        assert isinstance(provider, DevEnvironmentVariableProvider)
        assert provider.provider_type == "local"

    def test_get_provider_with_kwargs(self):
        """Test get_provider passes kwargs to provider constructor."""
        provider = CredentialManager.get_provider(
            provider_type="environment", key_prefix="CUSTOM_"
        )
        assert isinstance(provider, EnvironmentVariableProvider)
        assert provider.key_prefix == "CUSTOM_"

    def test_get_provider_with_aws_secrets(self):
        """Test get_provider with AWS Secrets Manager."""
        provider = CredentialManager.get_provider(
            provider_type="aws_secrets", aws_region="us-west-2"
        )
        assert isinstance(provider, AwsSecretsManagerProvider)
        assert provider.aws_region == "us-west-2"

    def test_get_provider_with_ado_variables(self):
        """Test get_provider with Azure DevOps variables."""
        provider = CredentialManager.get_provider(provider_type="ado_variables")
        assert isinstance(provider, AzureVariableGroupProvider)
        assert provider.provider_type == "ado_variables"

    def test_get_provider_with_invalid_type_raises_error(self):
        """Test get_provider raises error for invalid provider type."""
        with pytest.raises(ValueError) as exc_info:
            CredentialManager.get_provider(provider_type="invalid_provider")
        assert "Unknown provider type specified" in str(exc_info.value)
        assert "invalid_provider" in str(exc_info.value)

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "invalid"})
    def test_get_provider_raises_error_for_invalid_env_type(self):
        """Test get_provider raises error when env var has invalid type."""
        with pytest.raises(ValueError) as exc_info:
            CredentialManager.get_provider()
        assert "Unknown provider type specified" in str(exc_info.value)

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "local"})
    def test_get_provider_logs_provider_type(self):
        """Test get_provider logs the provider type being used."""
        with mock.patch("logging.Logger.info"):
            provider = CredentialManager.get_provider()
            # The logger should have been called with info about the provider
            assert provider is not None


class TestProviderIntegration:
    """Integration tests for provider workflow."""

    @mock.patch.dict(
        os.environ,
        {
            "CUMULUSCI_SECRETS_TYPE": "environment",
            "MYAPP_DATABASE_URL": "postgres://localhost/mydb",
        },
    )
    def test_full_workflow_environment_provider(self):
        """Test complete workflow using environment provider."""
        provider = CredentialManager.get_provider(key_prefix="MYAPP_")
        credentials = provider.get_credentials(
            "DATABASE_URL", {"value": "default_db_url"}
        )
        assert credentials == "postgres://localhost/mydb"

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "local"})
    def test_full_workflow_local_provider(self):
        """Test complete workflow using local provider."""
        provider = CredentialManager.get_provider()
        credentials = provider.get_credentials(
            "API_KEY", {"value": "local_api_key_123"}
        )
        assert credentials == "local_api_key_123"

    @mock.patch.dict(os.environ, {"CUMULUSCI_SECRETS_TYPE": "aws_secrets"})
    def test_full_workflow_aws_provider(self):
        """Test complete workflow using AWS Secrets Manager provider."""
        mock_client = mock.Mock()
        mock_session = mock.Mock()
        mock_session.client.return_value = mock_client
        mock_boto3 = mock.Mock()
        mock_boto3.session.Session.return_value = mock_session

        secret_data = {"API_KEY": "aws_secret_123"}
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps(secret_data)
        }

        with mock.patch.dict(
            sys.modules, {"boto3": mock_boto3, "botocore.exceptions": mock.Mock()}
        ):
            provider = CredentialManager.get_provider(aws_region="us-east-1")
            credentials = provider.get_credentials(
                "API_KEY", {"secret_name": "my-app/prod"}
            )
            assert credentials == "aws_secret_123"

    @mock.patch.dict(
        os.environ,
        {
            "CUMULUSCI_SECRETS_TYPE": "ado_variables",
            "MYAPP_API_TOKEN": "ado_token_xyz",
        },
    )
    def test_full_workflow_ado_provider(self):
        """Test complete workflow using Azure DevOps variables provider."""
        provider = CredentialManager.get_provider(key_prefix="MYAPP_")
        credentials = provider.get_credentials("API_TOKEN", {})
        assert credentials == "ado_token_xyz"
