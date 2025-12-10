import os
from pathlib import Path
from typing import Union

from dotenv import dotenv_values

from cumulusci.core.tasks import BaseTask
from cumulusci.utils.options import (
    CCIOptions,
    Field,
    ListOfStringsOption,
    MappingOption,
)

from .credentialManager import CredentialManager


class GenericOptions(CCIOptions):
    env_path: Path = Field("./.env", description="Path to the .env file")
    secrets_provider: str = Field(
        None,
        description='Secrets provider type i.e local, ado_variables, aws_secrets. Default value is None, which will use the secrets type from the environment variable CUMULUSCI_SECRETS_TYPE if it is set, otherwise it will use the "local" provider.',
    )
    provider_options: MappingOption = Field({}, description="Provider options")


class SecretsToEnv(BaseTask):
    class Options(GenericOptions):
        secrets: Union[ListOfStringsOption, MappingOption] = Field(
            ...,
            description="List of secret keys to retrieve be it with a list of keys or a mapping of key to secret name.",
        )

    parsed_options: Options

    def _init_options(self, kwargs):
        super()._init_options(kwargs)
        self.provider = CredentialManager.get_provider(
            self.parsed_options.secrets_provider
            or CredentialManager.load_secrets_type_from_environment(),
            **self.parsed_options.provider_options,
        )
        self.env_values = dotenv_values(self.parsed_options.env_path)

    def _init_secrets(self):
        if (
            isinstance(self.parsed_options.secrets, list)
            and self.parsed_options.secrets
        ):
            try:
                self.secrets = MappingOption.from_str(
                    ",".join(self.parsed_options.secrets)
                )
            except Exception:
                self.secrets = {
                    secret: secret for secret in self.parsed_options.secrets
                }
        elif isinstance(self.parsed_options.secrets, dict):
            self.secrets = self.parsed_options.secrets
        else:
            self.secrets = {}

    def _run_task(self):

        self._init_secrets()

        for secret_key, secret_name in self.secrets.items():
            if secret_key == "*":
                self.env_values.update(
                    self._get_all_credentials(secret_key, secret_name=secret_name)
                )
            else:
                self.env_values[secret_key] = self._get_credential(
                    secret_key, secret_key, secret_name=secret_name
                )
        self.return_values = {"env_values": self.env_values}
        self._write_env_file()

    def _write_env_file(self):
        safe_env_values = {}
        output_file = self.parsed_options.env_path

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

        # Write env file with UTF-8 encoding to support Unicode characters
        with open(output_file, "w", encoding="utf-8") as env_file:
            for key, value in self.env_values.items():
                safe_env_values[key] = self._escape_env_value(value)
                env_file.write(f'{key}="{safe_env_values[key]}"\n')

        self.return_values["safe_env_values"] = safe_env_values

    # https://pypi.org/project/python-dotenv/ -> README -> Escaping Values
    def _escape_env_value(self, value):
        """
        Escape special characters for .env file values in double quotes.
        Escapes: \\, \', \", \a, \b, \f, \n, \r, \t, \v
        """
        if not isinstance(value, str):
            return value

        escape_map = {
            "\\": "\\\\",  # Backslash must be first
            "'": "\\'",  # Single quote
            '"': '\\"',  # Double quote
            "\a": "\\a",  # Bell/Alert
            "\b": "\\b",  # Backspace
            "\f": "\\f",  # Form feed
            "\n": "\\n",  # Newline
            "\r": "\\r",  # Carriage return
            "\t": "\\t",  # Tab
            "\v": "\\v",  # Vertical tab
        }

        for char, escaped in escape_map.items():
            value = value.replace(char, escaped)

        return value

    def _get_credential(
        self,
        credential_key,
        value,
        env_key=None,
        display_value="*****",
        secret_name=None,
    ):
        if env_key is None:
            env_key = credential_key

        cred_secret_value = self.provider.get_credentials(
            credential_key, {"value": value, "secret_name": secret_name}
        )

        if cred_secret_value is None:
            raise ValueError(
                f"Failed to retrieve secret {credential_key} from {self.provider.provider_type}"
            )

        self.logger.info(
            f"Set secrets env var from {self.provider.provider_type}: {env_key}={display_value}"
        )
        return cred_secret_value

    def _get_all_credentials(
        self, credential_key, display_value="*****", secret_name=None
    ):

        cred_secret_values = self.provider.get_all_credentials(
            credential_key, {"secret_name": secret_name}
        )

        if cred_secret_values is None:
            raise ValueError(
                f"Failed to retrieve secret {credential_key}({secret_name}) from {self.provider.provider_type}"
            )

        dict_values = {}
        for key, value in cred_secret_values.items():
            self.logger.info(
                f"Set secrets env var from {self.provider.provider_type}: {key}={display_value}"
            )
            dict_values[key] = value

        return dict_values
