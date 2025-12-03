import os
from typing import Any, Dict, List, Optional

from pydantic.v1 import root_validator

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field


class ExtParameter(CCIOptions):
    """External Auth Identity Provider Parameter options"""

    name: str = Field(
        None,
        description="Parameter name. [default to None]",
    )
    value: str = Field(
        None,
        description="Parameter value. [default to None]",
    )
    sequence_number: int = Field(
        None,
        description="Sequence number. [default to None]",
    )


class ExternalAuthIdentityProviderCredential(CCIOptions):
    """External Auth Identity Provider Credential options"""

    name: str = Field(
        None,
        description="Credential name. [default to None]",
    )
    client_id: str = Field(
        None,
        description="Client ID. [default to None]",
    )
    client_secret: str = Field(
        None,
        description="Client secret. [default to None]",
    )
    auth_protocol: str = Field(
        "OAuth",
        description="Authentication protocol. [default to OAuth]",
    )


class ExternalAuthIdentityProviderParameter(CCIOptions):
    """External Auth Identity Provider Parameter options"""

    authorize_url: str = Field(
        None,
        description="Authorize URL. [default to None]",
    )
    token_url: str = Field(
        None,
        description="Token URL. [default to None]",
    )
    user_info_url: str = Field(
        None,
        description="User info URL. [default to None]",
    )
    jwks_url: str = Field(
        None,
        description="JWKS URL (for OpenID Connect). [default to None]",
    )
    issuer_url: str = Field(
        None,
        description="Issuer URL (for OpenID Connect). [default to None]",
    )
    client_authentication: str = Field(
        None,
        description="Client authentication method (e.g., ClientSecretBasic, ClientSecretPost, ClientSecretJwt). [default to None]",
    )
    custom_parameter: ExtParameter = Field(
        None,
        description="Custom parameter. [default to None]",
    )
    identity_provider_option: ExtParameter = Field(
        None,
        description="Identity provider option (e.g., PkceEnabled, UserinfoEnabled). [default to None]",
    )
    credential: ExternalAuthIdentityProviderCredential = Field(
        None,
        description="Credential to update. [default to None]",
    )
    secret: bool = Field(
        False,
        description="Is the value a secret. [default to False]",
    )

    @root_validator
    def check_parameters(cls, values):
        """Check if at least one parameter is provided"""
        param_fields = [
            "authorize_url",
            "token_url",
            "user_info_url",
            "jwks_url",
            "issuer_url",
            "client_authentication",
            "custom_parameter",
            "identity_provider_option",
            "credential",
        ]

        provided_params = [
            field for field in param_fields if values.get(field) is not None
        ]

        if len(provided_params) == 0:
            raise ValueError("At least and only one parameter must be provided.")

        if len(provided_params) > 1:
            raise ValueError("At least and only one parameter must be provided.")

        return values

    def get_external_auth_identity_provider_parameter(self):
        """Get the external auth identity provider parameter based on which field is set"""
        ext_auth_param = {}

        if self.authorize_url is not None:
            ext_auth_param["parameterType"] = "AuthorizeUrl"
            ext_auth_param["parameterName"] = "AuthorizeUrl"
            ext_auth_param["parameterValue"] = self.authorize_url

        if self.token_url is not None:
            ext_auth_param["parameterType"] = "TokenUrl"
            ext_auth_param["parameterName"] = "TokenUrl"
            ext_auth_param["parameterValue"] = self.token_url

        if self.user_info_url is not None:
            ext_auth_param["parameterType"] = "UserInfoUrl"
            ext_auth_param["parameterName"] = "UserInfoUrl"
            ext_auth_param["parameterValue"] = self.user_info_url

        if self.jwks_url is not None:
            ext_auth_param["parameterType"] = "JwksUrl"
            ext_auth_param["parameterName"] = "JwksUrl"
            ext_auth_param["parameterValue"] = self.jwks_url

        if self.issuer_url is not None:
            ext_auth_param["parameterType"] = "IssuerUrl"
            ext_auth_param["parameterName"] = "IssuerUrl"
            ext_auth_param["parameterValue"] = self.issuer_url

        if self.client_authentication is not None:
            ext_auth_param["parameterType"] = "ClientAuthentication"
            ext_auth_param["parameterName"] = "ClientAuthentication"
            ext_auth_param["parameterValue"] = self.client_authentication

        if self.custom_parameter is not None:
            ext_auth_param["parameterType"] = "CustomParameter"
            ext_auth_param["parameterName"] = self.custom_parameter.name
            ext_auth_param["parameterValue"] = self.custom_parameter.value
            if self.custom_parameter.sequence_number is not None:
                ext_auth_param["sequenceNumber"] = self.custom_parameter.sequence_number

        if self.identity_provider_option is not None:
            ext_auth_param["parameterType"] = "IdentityProviderOptions"
            ext_auth_param["parameterName"] = self.identity_provider_option.name
            ext_auth_param["parameterValue"] = self.identity_provider_option.value

        return ext_auth_param

    def get_credential(self, ext_auth_identity_provider_full_name: str):
        """Get the credential to update"""
        if self.credential is None:
            return None

        return {
            "credentials": [
                {
                    "credentialName": "clientId",
                    "credentialValue": self.credential.client_id,
                },
                {
                    "credentialName": "clientSecret",
                    "credentialValue": self.credential.client_secret,
                },
            ]
        }


class TransformExternalAuthIdentityProviderParameter(
    ExternalAuthIdentityProviderParameter
):
    """Transform External Auth Identity Provider Parameter with environment variable support"""

    def get_external_auth_identity_provider_parameter(self):
        ret = super().get_external_auth_identity_provider_parameter()
        if ret.get("parameterValue", None) is not None:
            ret["parameterValue"] = os.getenv(
                ret.get("parameterValue"), ret.get("parameterValue")
            )
        return ret

    def get_credential(self, ext_auth_identity_provider_full_name: str):
        """Get the credential with values from environment variables"""
        value = super().get_credential(ext_auth_identity_provider_full_name)

        if value is None:
            return None

        for credential in value["credentials"]:
            if credential["credentialValue"]:
                credential["credentialValue"] = os.getenv(
                    credential["credentialValue"], credential["credentialValue"]
                )

        return value


ExternalAuthIdentityProviderParameter.update_forward_refs()
TransformExternalAuthIdentityProviderParameter.update_forward_refs()


class UpdateExternalAuthIdentityProvider(BaseSalesforceApiTask):
    """Custom task to update external auth identity provider parameters.
    This task updates External Auth Identity Provider parameters and credentials using
    the Tooling API and Connect API.

    Reference:
    - https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/tooling_api_objects_externalauthidentityprovider.htm
    - https://developer.salesforce.com/docs/atlas.en-us.chatterapi.meta/chatterapi/connect_resources_named_credentials_external_auth_identity_provider_credentials.htm
    """

    class Options(CCIOptions):
        name: str = Field(
            ..., description="Name of the external auth identity provider to update."
        )
        namespace: str = Field(
            "",
            description="Namespace of the external auth identity provider to update. [default to empty string]",
        )
        # External auth identity provider parameters
        parameters: List[ExternalAuthIdentityProviderParameter] = Field(
            [],
            description="Parameters to update. [default to empty list]",
        )
        # Transform parameters (from environment variables)
        transform_parameters: List[
            TransformExternalAuthIdentityProviderParameter
        ] = Field(
            [],
            description="Parameters to transform from environment variables. [default to empty list]",
        )

    parsed_options: Options

    def _init_task(self):
        self.tooling = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
            api_version=self.project_config.project__package__api_version,
            base_url="tooling",
        )
        self.connect = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
            api_version=self.project_config.project__package__api_version,
        )

    def _run_task(self):
        # Step 1: Get the external auth identity provider id from the name
        ext_auth_id = self._get_external_auth_identity_provider_id()

        if not ext_auth_id:
            msg = f"External auth identity provider '{self.parsed_options.name}' not found"
            raise SalesforceDXException(msg)

        # Step 2: Get the external auth identity provider object
        ext_auth_provider = self._get_external_auth_identity_provider_object(
            ext_auth_id
        )

        if not ext_auth_provider:
            msg = f"Failed to retrieve external auth identity provider object for '{self.parsed_options.name}'"
            raise SalesforceDXException(msg)

        # Step 3: Update the external auth identity provider parameters
        self._update_external_auth_identity_provider_parameters(ext_auth_provider)

        updated_ext_auth_provider = self._update_external_auth_identity_provider_object(
            ext_auth_id, ext_auth_provider
        )

        if not updated_ext_auth_provider:
            msg = f"Failed to update external auth identity provider object for '{self.parsed_options.name}'"
            raise SalesforceDXException(msg)

        # Step 4: Update credentials if specified
        response = self._update_credential()

        if not response:
            raise SalesforceDXException(
                f"Failed to update credentials for external auth identity provider '{self.parsed_options.name}'"
            )

        self.logger.info(
            f"Successfully updated external auth identity provider '{self.parsed_options.name}'"
        )

    def _get_external_auth_identity_provider_id(self) -> Optional[str]:
        """Get the external auth identity provider ID from the name"""
        query = f"SELECT Id FROM ExternalAuthIdentityProvider WHERE DeveloperName='{self.parsed_options.name}'"

        if self.parsed_options.namespace:
            query += f" AND NamespacePrefix='{self.parsed_options.namespace}'"

        query += " LIMIT 1"

        try:
            res = self.tooling.query(query)
            if res["size"] == 0:
                return None
            return res["records"][0]["Id"]
        except Exception as e:
            self.logger.error(
                f"Error querying external auth identity provider: {str(e)}"
            )
            return None

    def _get_external_auth_identity_provider_object(
        self, ext_auth_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the external auth identity provider object using Tooling API"""
        try:
            # Use Tooling API to get the external auth identity provider metadata
            result = self.tooling._call_salesforce(
                method="GET",
                url=f"{self.tooling.base_url}sobjects/ExternalAuthIdentityProvider/{ext_auth_id}",
            )

            if result.status_code != 200:
                self.logger.error(
                    f"Error retrieving external auth identity provider object: {result.json()}"
                )
                return None

            return result.json().get("Metadata", None)

        except Exception as e:
            self.logger.error(
                f"Error retrieving external auth identity provider object: {str(e)}"
            )
            return None

    def _update_external_auth_identity_provider_object(
        self, ext_auth_id: str, ext_auth_provider: Dict[str, Any]
    ) -> Optional[bool]:
        """Update the external auth identity provider object"""
        try:
            result_update = self.tooling._call_salesforce(
                method="PATCH",
                url=f"{self.tooling.base_url}sobjects/ExternalAuthIdentityProvider/{ext_auth_id}",
                json={"Metadata": ext_auth_provider},
            )
            if not result_update.ok:
                self.logger.error(
                    f"Error updating external auth identity provider object: {result_update.json()}"
                )
                return None

            return result_update.ok
        except Exception as e:
            self.logger.error(
                f"Error updating external auth identity provider object: {str(e)}"
            )
            return None

    def _update_external_auth_identity_provider_parameters(
        self, ext_auth_provider: Dict[str, Any]
    ):
        """Update the external auth identity provider parameters"""
        try:
            # Get template parameter for new parameters
            template_param = (
                self._get_external_auth_identity_provider_template_parameter()
            )

            # Update regular parameters
            self._update_parameters(
                ext_auth_provider, self.parsed_options.parameters, template_param
            )

            # Update transform parameters (from environment variables)
            self._update_parameters(
                ext_auth_provider,
                self.parsed_options.transform_parameters,
                template_param,
            )

        except Exception as e:
            raise SalesforceDXException(f"Failed to update parameters: {str(e)}")

    def _update_parameters(
        self,
        ext_auth_provider: Dict[str, Any],
        ext_auth_parameters: List[ExternalAuthIdentityProviderParameter],
        template_param: Dict[str, Any],
    ):
        """Update the parameters"""
        for param_input in ext_auth_parameters:
            # Skip credential-only updates
            if param_input.credential is not None and all(
                getattr(param_input, field) is None
                for field in [
                    "authorize_url",
                    "token_url",
                    "user_info_url",
                    "jwks_url",
                    "issuer_url",
                    "client_authentication",
                    "custom_parameter",
                    "identity_provider_option",
                ]
            ):
                continue

            param_to_update = (
                param_input.get_external_auth_identity_provider_parameter()
            )
            secret = (
                param_to_update.pop("secret", False)
                if "secret" in param_to_update
                else False
            )

            # Create a copy for matching (without parameterValue and parameterName)
            param_to_match = {
                k: v
                for k, v in param_to_update.items()
                if k != "parameterValue" and k != "parameterName"
            }

            # Find existing parameter
            auth_param = next(
                (
                    param
                    for param in ext_auth_provider.get(
                        "externalAuthIdentityProviderParameters", []
                    )
                    if param_to_match.items() <= param.items()
                ),
                None,
            )

            if auth_param:
                # Update existing parameter
                auth_param.update(param_to_update)
                self.logger.info(
                    f"Updated parameter {auth_param['parameterType']}"
                    + (
                        f"-{auth_param.get('parameterName', 'N/A')}"
                        if auth_param.get("parameterName")
                        else ""
                    )
                    + f" with new value {param_to_update['parameterValue'] if not secret else '********'}"
                )
            else:
                # Add new parameter
                copy_template_param = template_param.copy()
                copy_template_param.update(param_to_update)
                if "externalAuthIdentityProviderParameters" not in ext_auth_provider:
                    ext_auth_provider["externalAuthIdentityProviderParameters"] = []
                ext_auth_provider["externalAuthIdentityProviderParameters"].append(
                    copy_template_param
                )
                self.logger.info(
                    f"Added parameter {copy_template_param['parameterType']}"
                    + (
                        f"-{copy_template_param.get('parameterName', 'N/A')}"
                        if copy_template_param.get("parameterName")
                        else ""
                    )
                    + f" with new value {param_to_update['parameterValue'] if not secret else '********'}"
                )

    def _get_external_auth_identity_provider_template_parameter(
        self,
    ) -> Dict[str, Any]:
        """Get the external auth identity provider template parameter"""
        return {
            "description": None,
            "parameterName": None,
            "parameterType": None,
            "parameterValue": None,
            "sequenceNumber": None,
        }

    def _update_credential(self):
        """Update the credential using Connect API"""
        for param in (
            self.parsed_options.parameters + self.parsed_options.transform_parameters
        ):
            if param.credential is None or (
                param.credential.client_secret is None
                and param.credential.client_id is None
            ):
                continue

            namespace = (
                f"{self.parsed_options.namespace}__"
                if self.parsed_options.namespace
                else ""
            )
            ext_auth_full_name = f"{namespace}{self.parsed_options.name}"

            self.logger.info(
                f"Managing credential for external auth identity provider {self.parsed_options.name}..."
            )

            # Get current credential
            credential_response = self.connect._call_salesforce(
                method="GET",
                url=f"{self.connect.base_url}named-credentials/external-auth-identity-provider-credentials/{ext_auth_full_name}",
            )

            if not credential_response.ok:
                msg = f"Failed to retrieve credential for {self.parsed_options.name}: {credential_response.json()}"
                raise SalesforceDXException(msg)

            credential = credential_response.json()
            http_verb = "PUT" if credential.get("credentials") else "POST"

            # Update credential data
            credential_data = param.get_credential(ext_auth_full_name)
            credential["credentials"] = credential_data["credentials"]

            # Update credential via Connect API
            try:
                response = self.connect._call_salesforce(
                    method=http_verb,
                    url=f"{self.connect.base_url}named-credentials/external-auth-identity-provider-credentials/{ext_auth_full_name}",
                    json=credential,
                )

                return response.ok

            except Exception as e:
                self.logger.error(
                    f"Error updating credential for {self.parsed_options.name}: {str(e)}"
                )
                return False

        # Return True if no credentials to update or all updates succeeded
        return True
