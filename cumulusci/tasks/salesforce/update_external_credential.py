import os
from typing import Any, Dict, List, Optional

from pydantic.v1 import root_validator

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field


class ExtParameter(CCIOptions):
    """Http Header options"""

    name: str = Field(
        None,
        description="Parameter name. [default to None]",
    )
    value: str = Field(
        None,
        description="Parameter value. [default to None]",
    )
    group: str = Field(
        None,
        description="Parameter group. [default to None]",
    )
    sequence_number: int = Field(
        None,
        description="Sequence number. [default to None]",
    )


class HttpHeader(ExtParameter):
    """Http Header options"""

    sequence_number: int = Field(
        None,
        description="Sequence number. [default to None]",
    )
    secret: bool = Field(
        False,
        description="Is the value a secret. [default to False]",
    )


class ExternalCredential(HttpHeader):
    client_secret: str = Field(
        None,
        description="Client secret. [default to None]",
    )
    client_id: str = Field(
        None,
        description="Client id. [default to None]",
    )
    auth_protocol: str = Field(
        "OAuth",
        description="Authentication protocol. [default to OAuth]",
    )


class ExternalCredentialParameter(CCIOptions):
    """External Credential Parameter options"""

    auth_header: HttpHeader = Field(
        None,
        description="Auth header value. [default to None]",
    )
    auth_provider: str = Field(
        None,
        description="Auth provider name (only subscriber editable in 2GP). [default to None]",
    )
    auth_provider_url: str = Field(
        None,
        description="Auth provider URL. [default to None]",
    )
    auth_provider_url_query_parameter: ExtParameter = Field(
        None,
        description="Auth provider URL query parameter, The allowed AuthProviderUrlQueryParameter values are AwsExternalId and AwsDuration, used with AWS STS. [default to None]",
    )
    auth_parameter: ExtParameter = Field(
        None,
        description="Auth parameter. Allows the user to add additional authentication settings. parameterName defines the parameter to set. [default to None]",
    )
    # aws_sts_principal: str = Field(
    #     None,
    #     description="AWS STS Principal (only for external credentials that use AWS Signature v4 authentication with STS). [default to None]",
    # )
    jwt_body_claim: ExtParameter = Field(
        None,
        description="Specifies a JWT (JSON Web Token) body claim. [default to None]",
    )
    jwt_header_claim: ExtParameter = Field(
        None,
        description="Specifies a JWT header claim. [default to None]",
    )
    named_principal: ExternalCredential = Field(
        None,
        description="Named principal. [default to None]",
    )
    per_user_principal: str = Field(
        None,
        description="Per user principal. [default to None]",
    )
    signing_certificate: str = Field(
        None,
        description="Signing certificate (only subscriber editable in 2GP). [default to None]",
    )
    secret: bool = Field(
        False,
        description="Is the value a secret. [default to False]",
    )

    @root_validator
    def check_parameters(cls, values):
        """Check if at least one parameter is provided"""
        param_fields = [
            "auth_header",
            "auth_provider",
            "auth_provider_url",
            "auth_provider_url_query_parameter",
            "auth_parameter",
            # "aws_sts_principal",
            "jwt_body_claim",
            "jwt_header_claim",
            "named_principal",
            "per_user_principal",
            "signing_certificate",
        ]

        provided_params = [
            field for field in param_fields if values.get(field) is not None
        ]

        if len(provided_params) == 0:
            raise ValueError("At least and only one parameter must be provided.")

        if len(provided_params) > 1:
            raise ValueError("At least and only one parameter must be provided.")

        return values

    def get_external_credential_parameter(self):
        ext_cred_param = {"parameterGroup": "DefaultGroup"}

        """Get the external credential parameter based on which field is set"""
        if self.auth_header is not None:
            ext_cred_param["parameterType"] = "AuthHeader"
            ext_cred_param["parameterValue"] = self.auth_header.value
            ext_cred_param["parameterName"] = self.auth_header.name

            if self.auth_header.sequence_number is not None:
                ext_cred_param["sequenceNumber"] = self.auth_header.sequence_number
            if self.auth_header.secret is not None:
                ext_cred_param["secret"] = self.auth_header.secret
            if self.auth_header.group is not None:
                ext_cred_param["parameterGroup"] = self.auth_header.group

        if self.auth_provider is not None:
            ext_cred_param["parameterType"] = "AuthProvider"
            ext_cred_param["parameterValue"] = self.auth_provider
            ext_cred_param["parameterName"] = "AuthProvider"
            ext_cred_param["authProvider"] = ext_cred_param["parameterValue"]

        if self.auth_provider_url is not None:
            ext_cred_param["parameterType"] = "AuthProviderUrl"
            ext_cred_param["parameterValue"] = self.auth_provider_url

        if self.auth_provider_url_query_parameter is not None:
            ext_cred_param["parameterType"] = "AuthProviderUrlQueryParameter"
            ext_cred_param[
                "parameterValue"
            ] = self.auth_provider_url_query_parameter.value
            ext_cred_param[
                "parameterName"
            ] = self.auth_provider_url_query_parameter.name

        if self.auth_parameter is not None:
            ext_cred_param["parameterType"] = "AuthParameter"
            ext_cred_param["parameterValue"] = self.auth_parameter.value
            ext_cred_param["parameterName"] = self.auth_parameter.name
            if self.auth_parameter.group is not None:
                ext_cred_param["parameterGroup"] = self.auth_parameter.group

        # if self.aws_sts_principal is not None:
        #     ext_cred_param["parameterType"] = "AwsStsPrincipal"
        #     ext_cred_param["parameterName"] = 'AwsStsPrincipal'
        #     ext_cred_param["parameterValue"] = self.aws_sts_principal

        if self.jwt_body_claim is not None:
            ext_cred_param["parameterType"] = "JwtBodyClaim"
            ext_cred_param["parameterName"] = self.jwt_body_claim.name
            ext_cred_param["parameterValue"] = self.jwt_body_claim.value

        if self.jwt_header_claim is not None:
            ext_cred_param["parameterType"] = "JwtHeaderClaim"
            ext_cred_param["parameterName"] = self.jwt_header_claim.name
            ext_cred_param["parameterValue"] = self.jwt_header_claim.value

        if self.named_principal is not None:
            ext_cred_param["parameterType"] = "NamedPrincipal"
            ext_cred_param["parameterName"] = self.named_principal.name
            ext_cred_param["parameterValue"] = None
            if self.named_principal.sequence_number is not None:
                ext_cred_param["sequenceNumber"] = self.named_principal.sequence_number
            ext_cred_param["parameterGroup"] = (
                self.named_principal.group
                if self.named_principal.group is not None
                else self.named_principal.name
            )

        if self.per_user_principal is not None:
            ext_cred_param["parameterType"] = "PerUserPrincipal"
            ext_cred_param["parameterName"] = "PerUserPrincipal"
            ext_cred_param["parameterGroup"] = "PerUser"
            ext_cred_param["parameterValue"] = self.per_user_principal

        if self.signing_certificate is not None:
            ext_cred_param["parameterType"] = "SigningCertificate"
            ext_cred_param["parameterName"] = "SigningCertificate"
            ext_cred_param["certificate"] = self.signing_certificate
            ext_cred_param["parameterValue"] = self.signing_certificate

        return ext_cred_param

    def get_principal_credential(self, ext_cred_full_name: str):
        if self.named_principal is None:
            return None

        return {
            "principalType": "NamedPrincipal",
            "principalName": self.named_principal.name,
            "externalCredential": ext_cred_full_name,
        }

    def get_credential_parameter(self):
        if self.named_principal is None or (
            self.named_principal.client_secret is None
            and self.named_principal.client_id is None
        ):
            return None

        return {
            "clientId": {"encrypted": False, "value": self.named_principal.client_id},
            "clientSecret": {
                "encrypted": True,
                "value": self.named_principal.client_secret,
            },
        }

    def get_credential(self, ext_cred_full_name: str):
        return {
            "authenticationProtocol": self.named_principal.auth_protocol,
            "credentials": self.get_credential_parameter(),
            "externalCredential": ext_cred_full_name,
            "principalName": self.named_principal.name,
            "principalType": "NamedPrincipal",
        }


class TransformExternalCredentialParameter(ExternalCredentialParameter):
    """Transform External Credential Parameter with environment variable support"""

    def get_external_credential_parameter(self):
        ret = super().get_external_credential_parameter()
        if ret.get("parameterValue", None) is not None:
            ret["parameterValue"] = os.getenv(ret.get("parameterValue"))
        return ret

    def get_credential_parameter(self):

        value = super().get_credential_parameter()

        if value is None:
            return None

        value["clientSecret"]["value"] = os.getenv(value["clientSecret"]["value"])
        value["clientId"]["value"] = os.getenv(
            value["clientId"]["value"], value["clientId"]["value"]
        )

        return value


ExternalCredentialParameter.update_forward_refs()
TransformExternalCredentialParameter.update_forward_refs()


class UpdateExternalCredential(BaseSalesforceApiTask):
    """Custom task to update external credential parameters.
    This task is based on the manageability rules of external credentials in 2GP.
    https://developer.salesforce.com/docs/atlas.en-us.pkg2_dev.meta/pkg2_dev/packaging_packageable_components.htm#mdc_external_credential
    """

    class Options(CCIOptions):
        name: str = Field(..., description="Name of the external credential to update.")
        namespace: str = Field(
            "",
            description="Namespace of the external credential to update. [default to empty string]",
        )
        # External credential parameters
        parameters: List[ExternalCredentialParameter] = Field(
            [],
            description="Parameters to update. [default to empty list]",
        )
        # Transform parameters (from environment variables)
        transform_parameters: List[TransformExternalCredentialParameter] = Field(
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
        # Step 1: Get the external credential id from the external credential name
        external_credential_id = self._get_external_credential_id()

        if not external_credential_id:
            msg = f"External credential '{self.parsed_options.name}' not found"
            raise SalesforceDXException(msg)

        # Step 2: Get the external credential object
        external_credential = self._get_external_credential_object(
            external_credential_id
        )

        if not external_credential:
            msg = f"Failed to retrieve external credential object for '{self.parsed_options.name}'"
            raise SalesforceDXException(msg)

        # Step 3: Update the external credential parameters
        self._update_external_credential_parameters(external_credential)

        updated_external_credential = self._update_external_credential_object(
            external_credential_id, external_credential
        )

        if not updated_external_credential:
            msg = f"Failed to update external credential object for '{self.parsed_options.name}'"
            raise SalesforceDXException(msg)

        self._update_credential()

        self.logger.info(
            f"Successfully updated external credential '{self.parsed_options.name}'"
        )

    def _get_external_credential_id(self) -> Optional[str]:
        """Get the external credential ID from the external credential name"""
        query = f"SELECT Id FROM ExternalCredential WHERE DeveloperName='{self.parsed_options.name}'"

        if self.parsed_options.namespace:
            query += f" AND NamespacePrefix='{self.parsed_options.namespace}'"

        query += " LIMIT 1"

        try:
            res = self.tooling.query(query)
            if res["size"] == 0:
                return None
            return res["records"][0]["Id"]
        except Exception as e:
            self.logger.error(f"Error querying external credential: {str(e)}")
            return None

    def _get_external_credential_object(
        self, external_credential_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the external credential object using Tooling API"""
        try:
            # Use Tooling API to get the external credential metadata
            result = self.tooling._call_salesforce(
                method="GET",
                url=f"{self.tooling.base_url}sobjects/ExternalCredential/{external_credential_id}",
            )

            if result.status_code != 200:
                self.logger.error(
                    f"Error retrieving external credential object: {result.json()}"
                )
                return None

            return result.json().get("Metadata", None)

        except Exception as e:
            self.logger.error(f"Error retrieving external credential object: {str(e)}")
            return None

    def _update_external_credential_object(
        self, external_credential_id: str, external_credential: Dict[str, Any]
    ) -> Optional[bool]:
        """Update the external credential object"""
        try:
            result_update = self.tooling._call_salesforce(
                method="PATCH",
                url=f"{self.tooling.base_url}sobjects/ExternalCredential/{external_credential_id}",
                json={"Metadata": external_credential},
            )
            if not result_update.ok:
                self.logger.error(
                    f"Error updating external credential object: {result_update.json()}"
                )
                return None

            return result_update.ok
        except Exception as e:
            raise SalesforceDXException(
                f"Failed to update external credential object: {str(e)}"
            )

    def _update_external_credential_parameters(
        self, external_credential: Dict[str, Any]
    ):
        """Update the external credential parameters"""
        try:
            # Get template parameter for new parameters
            template_param = self._get_external_credential_template_parameter()

            # Update regular parameters
            self._update_parameters(
                external_credential, self.parsed_options.parameters, template_param
            )

            # Update transform parameters (from environment variables)
            self._update_parameters(
                external_credential,
                self.parsed_options.transform_parameters,
                template_param,
            )

        except Exception as e:
            raise SalesforceDXException(f"Failed to update parameters: {str(e)}")

    def _update_parameters(
        self,
        external_credential: Dict[str, Any],
        external_credential_parameters: List[ExternalCredentialParameter],
        template_param: Dict[str, Any],
    ):
        """Update the parameters"""
        for param_input in external_credential_parameters:
            param_to_update = param_input.get_external_credential_parameter()
            secret = param_to_update.pop("secret", False)

            # Create a copy for matching (without parameterValue)
            param_to_match = {
                k: v for k, v in param_to_update.items() if k != "parameterValue"
            }

            # Find existing parameter
            cred_param = next(
                (
                    param
                    for param in external_credential.get(
                        "externalCredentialParameters", []
                    )
                    if param_to_match.items() <= param.items()
                ),
                None,
            )

            if cred_param:
                # Update existing parameter
                cred_param.update(param_to_update)
                self.logger.info(
                    f"Updated parameter {cred_param['parameterType']}"
                    + (
                        f"-{cred_param.get('parameterName', 'N/A')}"
                        if cred_param.get("parameterName")
                        else ""
                    )
                    + f" with new value {param_to_update['parameterValue'] if not secret else '********'}"
                )
            else:
                # Add new parameter
                copy_template_param = template_param.copy()
                copy_template_param.update(param_to_update)
                if "externalCredentialParameters" not in external_credential:
                    external_credential["externalCredentialParameters"] = []
                external_credential["externalCredentialParameters"].append(
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

    def _get_external_credential_template_parameter(self) -> Dict[str, Any]:
        """Get the external credential template parameter"""
        return {
            "authProvider": None,
            "certificate": None,
            "description": None,
            "externalAuthIdentityProvider": None,
            "parameterGroup": None,
            "parameterName": None,
            "parameterType": None,
            "parameterValue": None,
            "sequenceNumber": None,
        }

    def _update_credential(self):
        """Update the credential"""
        for param in (
            self.parsed_options.parameters + self.parsed_options.transform_parameters
        ):
            if param.named_principal is None or (
                param.named_principal.client_secret is None
                and param.named_principal.client_id is None
            ):
                continue

            namespace = (
                f"{self.parsed_options.namespace}__"
                if self.parsed_options.namespace
                else ""
            )
            credential_param = param.get_principal_credential(
                f"{namespace}{self.parsed_options.name}"
            )

            self.logger.info(f"Managing credential for {param.named_principal.name}...")

            credential_response = self.connect._call_salesforce(
                method="GET",
                url=f"{self.connect.base_url}named-credentials/credential",
                params=credential_param,
            )

            credential = credential_response.json()
            credential.pop("authenticationStatus")
            http_verb = "PUT" if credential["credentials"] else "POST"
            credential["credentials"] = param.get_credential_parameter()

            response = self.connect._call_salesforce(
                method=http_verb,
                url=f"{self.connect.base_url}named-credentials/credential",
                json=credential,
            )

            if not response.ok:
                msg = f"Failed to update credential {param.named_principal.name}: {response.json()}"
                raise SalesforceDXException(msg)

            self.logger.info(f"Updated credential {param.named_principal.name}")
