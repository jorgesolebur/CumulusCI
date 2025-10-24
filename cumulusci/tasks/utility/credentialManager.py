import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional


# Abstract Base Class for Credential Providers
class CredentialProvider(ABC):
    """
    Abstract Base Class that defines the interface for all credential providers.
    """

    # A class-level dictionary to store a mapping of provider names to provider classes
    _registry = {}
    logger: logging.Logger

    def __init__(self, **kwargs):
        self.key_prefix = kwargs.get(
            "key_prefix", os.getenv("CUMULUSCI_PREFIX_SECRETS", "").upper()
        )
        self.logger = logging.getLogger(__name__)

    def __init_subclass__(cls, **kwargs):
        """
        This method is called automatically when a new class inherits from CredentialProvider.
        It's used to register the new class in our registry.
        """
        super().__init_subclass__(**kwargs)
        # We'll use an attribute on each class to define its provider type.
        # This will be the key in our registry.
        if hasattr(cls, "provider_type"):
            CredentialProvider._registry[cls.provider_type] = cls

    @abstractmethod
    def get_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """
        Retrieves and returns credentials.
        """
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def get_all_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """
        Retrieves and returns all credentials in a group, for example all secrets in AWS secret.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def get_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"


# Concrete Credential Provider for Local Development
class DevEnvironmentVariableProvider(CredentialProvider):
    """
    Retrieves secrets from environment variables.
    This is suitable for local development.
    """

    provider_type = "local"

    def get_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        value = options.get("value", None)
        self.logger.info(f"Credentials for {key} from local environment is {value}.")
        return value

    def get_all_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """Local provider doesn't support retrieving all credentials."""
        raise NotImplementedError("Local provider doesn't support get_all_credentials")


# Concrete Credential Provider for Local Development
class EnvironmentVariableProvider(CredentialProvider):
    """
    Retrieves secrets from environment variables.
    This is suitable for local development.
    """

    provider_type = "environment"

    def get_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        value = options.get("value", None)
        ret_value = os.getenv(self.get_key(key))
        if ret_value is None:
            self.logger.info(f"Credentials for {key} from environment is {value}.")
        return ret_value or value

    def get_all_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """Environment provider doesn't support retrieving all credentials."""
        raise NotImplementedError(
            "Environment provider doesn't support get_all_credentials"
        )


# Concrete Credential Provider for Azure Pipelines
class AwsSecretsManagerProvider(CredentialProvider):
    """
    Retrieves secrets from AWS Secrets Manager.
    This is designed for use in a CI/CD environment like Azure Pipelines,
    where a Service Connection provides a role to assume.
    """

    provider_type = "aws_secrets"
    secrets_cache: dict[str, dict[str, Any]]
    aws_region: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secrets_cache = kwargs.get("secrets_cache", {})

        self.aws_region = kwargs.get("aws_region", os.getenv("AWS_REGION", None))
        if self.aws_region is None:
            raise ValueError(
                "AWS_REGION environment variable or aws_region option is required for AWS Secrets Manager."
            )

    def get_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """
        Connects to AWS Secrets Manager to retrieve a secret.
        The boto3 client automatically uses the credentials provided by the
        Azure DevOps AWS Service Connection (e.g., through OIDC or static keys).
        """
        return self.aws_creds(key, options).get(key, None)

    def get_all_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        return self.aws_creds(key, options)

    def aws_creds(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        secret_name = options.get("secret_name", None)
        if secret_name is None:
            raise ValueError("Secret name is required for AWS Secrets Manager.")

        try:
            if secret_name in self.secrets_cache:
                return self.secrets_cache[secret_name]

            import json

            import boto3
            from botocore.exceptions import ClientError

            # Boto3 automatically handles credential lookup. In an Azure Pipeline,
            # it will find the temporary credentials provided by the AWS Service Connection.
            # Create a Secrets Manager client
            session = boto3.session.Session()
            client = session.client(
                service_name="secretsmanager", region_name=self.aws_region
            )

            get_secret_value_response = client.get_secret_value(SecretId=secret_name)

            secret = get_secret_value_response["SecretString"]

            # Assuming the secret is a JSON string with the credentials
            # We need to check the binary type of the secret at later development
            self.secrets_cache[secret_name] = json.loads(secret)

            return self.secrets_cache[secret_name]
        except ClientError as e:
            # For a list of exceptions thrown, see
            # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
            raise e
        except ImportError:
            raise RuntimeError(
                "boto3 is not installed. Please install it using 'pip install boto3' or 'pipx inject cumulusci-plus-azure-devops boto3'."
            )
        except Exception as e:
            raise RuntimeError(f"Failed to retrieve secret '{key}': {e}")


# Concrete Credential Provider for Azure Variable Groups
class AzureVariableGroupProvider(CredentialProvider):
    """
    Retrieves secrets from Azure Pipeline Variable Groups.
    When a variable group is linked, its variables are exposed as
    environment variables in the pipeline job.
    """

    provider_type = "ado_variables"

    def get_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """
        Looks for AWS credentials in environment variables exposed by
        an Azure variable group.
        """
        # Azure pipelines convert variable names to uppercase and replace dots with underscores.
        key_env_var = self.get_key(key)
        return os.getenv(key_env_var.upper().replace(".", "_"))

    def get_all_credentials(
        self, key: str, options: Optional[dict[str, Any]] = None
    ) -> Any:
        """Azure variable group provider doesn't support retrieving all credentials."""
        raise NotImplementedError(
            "Azure variable group provider doesn't support get_all_credentials"
        )


# The CredentialManager to select the right provider
class CredentialManager:
    """
    Factory class to determine and return the correct CredentialProvider based on the environment.
    """

    env_secrets_type = "CUMULUSCI_SECRETS_TYPE"

    @staticmethod
    def load_secrets_type_from_environment() -> str:
        """Load any secrets specified by environment variables"""
        provider_type = os.getenv(CredentialManager.env_secrets_type)

        # If no provider type is found, use the dev provider
        return (provider_type or "local").lower()

    @staticmethod
    def get_provider(
        provider_type: Optional[str] = None, **kwargs
    ) -> CredentialProvider:
        """
        Looks up the provider class in the registry and returns an instance.
        """
        if not provider_type:
            # If no config is provided, load the secrets from the environment
            provider_type = CredentialManager.load_secrets_type_from_environment()

        # Check if the requested provider type exists in our registry
        if provider_type not in CredentialProvider._registry:
            raise ValueError(f"Unknown provider type specified: '{provider_type}'")

        # Get the class from the registry
        ProviderClass = CredentialProvider._registry[provider_type]
        provider = ProviderClass(**kwargs)
        provider.logger.info(
            f'Using "{provider.provider_type}" provider for credentials.'
        )

        return provider
