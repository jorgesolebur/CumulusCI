import os
from typing import Any, Dict, List, Optional

from pydantic.v1 import root_validator

from cumulusci.core.exceptions import SalesforceDXException
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.tasks.salesforce import BaseSalesforceApiTask
from cumulusci.utils.options import CCIOptions, Field


class NamedCredentialCalloutOptions(CCIOptions):
    # Callout options
    allow_merge_fields_in_body: bool = Field(
        None,
        description="Allow merge fields in body. [default to None]",
    )
    allow_merge_fields_in_header: bool = Field(
        None,
        description="Allow merge fields in header. [default to None]",
    )
    generate_authorization_header: bool = Field(
        None,
        description="Generate authorization header. [default to None]",
    )


class NamedCredentialHttpHeader(CCIOptions):
    name: str = Field(
        None,
        description="Name. [default to None]",
    )
    value: str = Field(
        None,
        description="Value. [default to None]",
    )
    sequence_number: int = Field(
        None,
        description="Sequence number. [default to None]",
    )
    secret: bool = Field(
        False,
        description="Is the value a secret. [default to False]",
    )


class NamedCredentialParameter(CCIOptions):
    allowed_managed_package_namespaces: str = Field(
        None,
        description="Allowed managed package namespaces. [default to None]",
    )
    url: str = Field(
        None,
        description="Url. [default to None]",
    )
    authentication: str = Field(
        None,
        description="Authentication. [default to None]",
    )
    certificate: str = Field(
        None,
        description="Certificate. [default to None]",
    )
    http_header: List["NamedCredentialHttpHeader"] = Field(
        [],
        description="Http header. [default to empty list]",
    )

    @root_validator
    def check_parameters(cls, values):
        """Check if only one of the parameters is provided"""
        if (
            len(
                ([values.get("url")] if values.get("url") else [])
                + (
                    [values.get("allowed_managed_package_namespaces")]
                    if values.get("allowed_managed_package_namespaces")
                    else []
                )
                + (
                    [values.get("authentication")]
                    if values.get("authentication")
                    else []
                )
                + ([values.get("certificate")] if values.get("certificate") else [])
                + (
                    [len(values.get("http_header"))]
                    if values.get("http_header")
                    else []
                )
            )
            == 1
        ):
            return values
        raise ValueError("Only one of the parameters is required.")

    def param_type(self):
        """Get the parameter type"""
        if self.url:
            return "Url"
        if self.authentication:
            return "Authentication"
        if self.certificate:
            return "ClientCertificate"
        if self.allowed_managed_package_namespaces:
            return "AllowedManagedPackageNamespaces"
        if self.http_header:
            return "HttpHeader"

        return None

    def param_value(self, http_header=None):
        """Get the parameter value"""
        if self.url:
            return self.url
        if self.authentication:
            return self.authentication
        if self.certificate:
            return self.certificate
        if self.allowed_managed_package_namespaces:
            return self.allowed_managed_package_namespaces
        if http_header:
            http_header_item = next(
                (item for item in self.http_header if item.name == http_header), None
            )
            if http_header_item:
                return http_header_item.value

    def get_parameter_to_update(self):
        """Get the parameter to update"""
        ret = []

        if len(self.http_header) > 0:
            for http_header_item in self.http_header:
                param_to_update = {}
                param_to_update["parameterName"] = http_header_item.name
                param_to_update["parameterType"] = "HttpHeader"
                param_to_update["parameterValue"] = self.param_value(
                    http_header=http_header_item.name
                )
                param_to_update["secret"] = http_header_item.secret

                if http_header_item.sequence_number is not None:
                    param_to_update["sequenceNumber"] = http_header_item.sequence_number

                ret.append(param_to_update.copy())
        else:
            param_to_update = {}
            param_to_update["parameterType"] = self.param_type()
            param_to_update["parameterValue"] = self.param_value()

            if param_to_update["parameterType"] == "ClientCertificate":
                param_to_update["parameterName"] = "ClientCertificate"
                param_to_update["certificate"] = param_to_update["parameterValue"]

            if param_to_update["parameterType"] == "Authentication":
                param_to_update["parameterName"] = "ExternalCredential"
                param_to_update["externalCredential"] = param_to_update[
                    "parameterValue"
                ]

            ret.append(param_to_update.copy())

        return ret


class TransformNamedCredentialParameter(NamedCredentialParameter):
    def param_value(self, http_header=None):
        value = super().param_value(http_header)
        if value:
            return os.getenv(value)
        return None


NamedCredentialParameter.update_forward_refs()
TransformNamedCredentialParameter.update_forward_refs()


class UpdateNamedCredential(BaseSalesforceApiTask):
    """Custom task to update named credential parameters.
    This task is based on the managability rules of named credentials.
    https://developer.salesforce.com/docs/atlas.en-us.pkg2_dev.meta/pkg2_dev/packaging_packageable_components.htm#mdc_named_credential
    """

    class Options(CCIOptions):
        name: str = Field(..., description="Name of the named credential to update.")
        namespace: str = Field(
            "",
            description="Namespace of the named credential to update. [default to empty string]",
        )
        # Callout options
        callout_options: NamedCredentialCalloutOptions = Field(
            None,
            description="Callout options. [default to None]",
        )
        # Named credential parameters
        parameters: List[NamedCredentialParameter] = Field(
            [],
            description="Parameters to update. [default to empty list]",
        )
        # Named credential parameters
        transform_parameters: List[TransformNamedCredentialParameter] = Field(
            [],
            description="Parameters to transform. [default to empty list]",
        )

    parsed_options: Options

    def _init_task(self):
        self.tooling = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
            api_version=self.project_config.project__package__api_version,
            base_url="tooling",
        )

    def _run_task(self):
        # Step 1: Get the named credential id from the named credential name
        named_credential_id = self._get_named_credential_id()

        if not named_credential_id:
            msg = f"Named credential '{self.parsed_options.name}' not found"
            raise SalesforceDXException(msg)

        # Step 2: Get the named credential object
        named_credential = self._get_named_credential_object(named_credential_id)

        if not named_credential:
            msg = f"Failed to retrieve named credential object for '{self.parsed_options.name}'"
            raise SalesforceDXException(msg)

        if named_credential.get("namedCredentialType") != "SecuredEndpoint":
            msg = f"Named credential '{self.parsed_options.name}' is not a secured endpoint, Aborting update. Only SecuredEndpoint is supported."
            raise SalesforceDXException(msg)

        # Step 3: Update the named credential parameters
        self._update_named_credential_parameters(named_credential)

        updated_named_credential = self._update_named_credential_object(
            named_credential_id, named_credential
        )

        if not updated_named_credential:
            msg = f"Failed to update named credential object for '{self.parsed_options.name}'"
            raise SalesforceDXException(msg)

        self.logger.info(
            f"Successfully updated named credential '{self.parsed_options.name}'"
        )

    def _get_named_credential_id(self) -> Optional[str]:
        """Get the named credential ID from the named credential name"""
        query = f"SELECT Id FROM NamedCredential WHERE DeveloperName='{self.parsed_options.name}'"

        if self.parsed_options.namespace:
            query += f" AND NamespacePrefix='{self.parsed_options.namespace}'"

        query += " LIMIT 1"

        try:
            res = self.tooling.query(query)
            if res["size"] == 0:
                return None
            return res["records"][0]["Id"]
        except Exception as e:
            self.logger.error(f"Error querying named credential: {str(e)}")
            return None

    def _get_named_credential_object(
        self, named_credential_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the named credential object using Metadata API"""
        try:
            # Use Tooling API to get the named credential metadata
            result = self.tooling._call_salesforce(
                method="GET",
                url=f"{self.tooling.base_url}sobjects/NamedCredential/{named_credential_id}",
            )

            if result.status_code != 200:
                self.logger.error(
                    f"Error retrieving named credential object: {result.json()}"
                )
                return None

            return result.json().get("Metadata", None)

        except Exception as e:
            self.logger.error(f"Error retrieving named credential object: {str(e)}")
            return None

    def _update_named_credential_object(
        self, named_credential_id: str, named_credential: Dict[str, Any]
    ) -> Optional[bool]:
        """Update the named credential object"""
        try:
            resultUpdate = self.tooling._call_salesforce(
                method="PATCH",
                url=f"{self.tooling.base_url}sobjects/NamedCredential/{named_credential_id}",
                json={"Metadata": named_credential},
            )
            if not resultUpdate.ok:
                self.logger.error(
                    f"Error updating named credential object: {resultUpdate.json()}"
                )
                return None

            return resultUpdate.ok
        except Exception as e:
            raise SalesforceDXException(
                f"Failed to update named credential object: {str(e)}"
            )

    def _update_named_credential_parameters(self, named_credential: Dict[str, Any]):
        """Update the named credential parameters"""
        try:
            template_param = self._get_named_credential_template_parameter(
                named_credential
            )

            self._update_callout_options(named_credential)
            self._update_parameters(
                named_credential, self.parsed_options.parameters, template_param
            )
            self._update_parameters(
                named_credential,
                self.parsed_options.transform_parameters,
                template_param,
            )

        except Exception as e:
            raise SalesforceDXException(f"Failed to update parameters: {str(e)}")

    def _update_callout_options(self, named_credential: Dict[str, Any]):
        """Update the callout options"""
        if not self.parsed_options.callout_options:
            return

        if self.parsed_options.callout_options.allow_merge_fields_in_body:
            named_credential[
                "allowMergeFieldsInBody"
            ] = self.parsed_options.callout_options.allow_merge_fields_in_body
        if self.parsed_options.callout_options.allow_merge_fields_in_header:
            named_credential[
                "allowMergeFieldsInHeader"
            ] = self.parsed_options.callout_options.allow_merge_fields_in_header
        if self.parsed_options.callout_options.generate_authorization_header:
            named_credential[
                "generateAuthorizationHeader"
            ] = self.parsed_options.callout_options.generate_authorization_header

    def _update_parameters(
        self,
        named_credential: Dict[str, Any],
        named_credential_parameters: List[NamedCredentialParameter],
        template_param: Dict[str, Any],
    ):
        """Update the parameters"""
        for param_input in named_credential_parameters:
            params_to_update = param_input.get_parameter_to_update()

            for param_to_update in params_to_update:
                secret = param_to_update.pop("secret", False)

                param_to_update_copy = param_to_update.copy()
                param_to_update_copy.pop("parameterValue", None)
                param_to_update_copy.pop("certificate", None)
                param_to_update_copy.pop("externalCredential", None)

                cred_param = next(
                    (
                        param
                        for param in named_credential.get(
                            "namedCredentialParameters", []
                        )
                        if param_to_update_copy.items() <= param.items()
                    ),
                    None,
                )

                if cred_param:
                    cred_param.update(param_to_update)
                    self.logger.info(
                        f"Updated parameter {cred_param['parameterType']}-{cred_param['parameterName']} with new value {param_to_update['parameterValue'] if not secret else '********'}"
                    )
                else:
                    copy_template_param = template_param.copy()
                    copy_template_param.update(param_to_update)
                    named_credential["namedCredentialParameters"].append(
                        copy_template_param
                    )
                    self.logger.info(
                        f"Added parameter {copy_template_param['parameterType']}-{copy_template_param['parameterName']} with new value {param_to_update['parameterValue'] if not secret else '********'}"
                    )

    def _update_parameter_value(
        self, named_credential_parameter: Dict[str, Any], new_value: str
    ):
        """Update an existing parameter's value"""
        update_data = {"parameterValue": new_value}
        named_credential_parameter.update(update_data)

    def _get_named_credential_template_parameter(
        self, named_credential: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get the named credential template parameter"""
        template_param = [
            param
            for param in named_credential.get("namedCredentialParameters", [])
            if param.get("parameterType") == "Url"
        ]
        if len(template_param) == 0:
            self.logger.warning(
                f"No template parameter found for named credential '{self.parsed_options.name}', using default template parameter."
            )
            return {
                "certificate": None,
                "description": None,
                "externalCredential": None,
                "globalNamedPrincipalCredential": None,
                "managedFeatureEnabledCallout": None,
                "outboundNetworkConnection": None,
                "parameterName": None,
                "parameterType": None,
                "parameterValue": None,
                "readOnlyNamedCredential": None,
                "sequenceNumber": None,
                "systemUserNamedCredential": None,
            }

        ret = template_param[0].copy()
        ret.update(
            {
                "parameterName": None,
                "parameterType": None,
                "parameterValue": None,
                "sequenceNumber": None,
            }
        )

        return ret
