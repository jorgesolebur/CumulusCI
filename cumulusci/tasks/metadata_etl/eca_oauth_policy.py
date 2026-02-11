"""Update ExtlClntAppOauthConfigurablePolicies metadata."""

from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.core.utils import process_bool_arg, process_list_arg
from cumulusci.salesforce_api.utils import get_simple_salesforce_connection
from cumulusci.tasks.metadata_etl import MetadataSingleEntityTransformTask
from cumulusci.utils.xml.metadata_tree import MetadataElement

# String and boolean fields from ExtlClntAppOauthConfigurablePolicies metadata API
# https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_extlclntappoauthconfigurablepolicies.htm
ECA_OAUTH_STRING_FIELDS = [
    "commaSeparatedPermissionSet",
    "externalClientApplication",
    "ipRelaxationPolicyType",
    "label",
    "permittedUsersPolicyType",
    "refreshTokenPolicyType",
    "refreshTokenValidityPeriod",
    "refreshTokenValidityUnit",
    "requiredSessionLevel",
]
ECA_OAUTH_BOOLEAN_FIELDS = [
    "isClientCredentialsFlowEnabled",
    "isGuestCodeCredFlowEnabled",
    "isTokenExchangeFlowEnabled",
]
# User reference fields - accept user_alias, resolve to Username via SOQL
ECA_OAUTH_USER_FIELDS = {
    "executeHandlerAs": "execute_handler_as_user_alias",
    "clientCredentialsFlowUser": "client_credentials_flow_user_alias",
}


class UpdateEcaOauthPolicy(MetadataSingleEntityTransformTask):
    """Update ExtlClntAppOauthConfigurablePolicies metadata.

    Supports string and boolean fields. For executeHandlerAs and
    clientCredentialsFlowUser, pass the corresponding user_alias option
    and the task will query the User by Alias and populate the Username.
    """

    entity = "ExtlClntAppOauthConfigurablePolicies"

    task_options = {
        "comma_separated_permission_set": {
            "description": "Comma-separated list of permission set API names"
        },
        "external_client_application": {
            "description": "External Client Application developer name"
        },
        "ip_relaxation_policy_type": {
            "description": "IP relaxation policy (e.g. Bypass)"
        },
        "label": {"description": "Label for the OAuth policy"},
        "permitted_users_policy_type": {
            "description": "Permitted users policy (e.g. AdminApprovedPreAuthorized)"
        },
        "refresh_token_policy_type": {
            "description": "Refresh token policy (e.g. SpecificLifetime)"
        },
        "refresh_token_validity_period": {
            "description": "Refresh token validity period value"
        },
        "refresh_token_validity_unit": {
            "description": "Refresh token validity unit (e.g. Days)"
        },
        "required_session_level": {
            "description": "Required session level (e.g. STANDARD)"
        },
        "is_client_credentials_flow_enabled": {
            "description": "Enable client credentials flow (boolean)"
        },
        "is_guest_code_cred_flow_enabled": {
            "description": "Enable guest code credential flow (boolean)"
        },
        "is_token_exchange_flow_enabled": {
            "description": "Enable token exchange flow (boolean)"
        },
        "execute_handler_as_user_alias": {
            "description": "User alias for executeHandlerAs - resolves to Username"
        },
        "client_credentials_flow_user_alias": {
            "description": "User alias for clientCredentialsFlowUser - resolves to Username"
        },
        "api_names": {
            "description": "List of External Client Application names (e.g. SelfCallout). _oauth_defaultPolicy is appended to form the OAuth policy name."
        },
        **{
            k: v
            for k, v in MetadataSingleEntityTransformTask.task_options.items()
            if k != "api_names"
        },
    }

    def _init_options(self, kwargs):
        # api_names accepts External Client Application names (e.g. SelfCallout)
        # Append _oauth_defaultPolicy so parent processes full policy names (e.g. SelfCallout_oauth_defaultPolicy)
        suffix = "_oauth_defaultPolicy"
        api_names_raw = process_list_arg(self.task_config.options.get("api_names", []))
        api_names_with_suffix = [
            name if str(name).endswith(suffix) else f"{name}{suffix}"
            for name in api_names_raw
        ]
        kwargs["api_names"] = api_names_with_suffix

        super()._init_options(kwargs)
        if not any(
            self.options.get(opt)
            for opt in (
                list(ECA_OAUTH_USER_FIELDS.values())
                + [self._to_option_name(f) for f in ECA_OAUTH_STRING_FIELDS]
                + [self._to_option_name(f) for f in ECA_OAUTH_BOOLEAN_FIELDS]
            )
        ):
            raise TaskOptionsError(
                "At least one update option must be provided. "
                "See task options for available fields."
            )

        self.sf = get_simple_salesforce_connection(
            self.project_config,
            self.org_config,
        )

    def _to_option_name(self, metadata_field: str) -> str:
        """Convert metadata field name to task option name."""
        result = metadata_field[0].lower()
        for c in metadata_field[1:]:
            if c.isupper():
                result += "_" + c.lower()
            else:
                result += c
        return result

    def _to_metadata_field(self, option_name: str) -> str:
        """Convert task option name to metadata field name."""
        parts = option_name.split("_")
        return "".join(p.capitalize() for p in parts)

    def _get_username_by_alias(self, user_alias: str) -> str:
        """Query User by Alias and return Username."""
        # Escape single quotes for SOQL safety (SOQL uses '' for escaped ')
        escaped_alias = user_alias.replace("'", "''")
        query = (
            f"SELECT Username FROM User "
            f"WHERE Alias = '{escaped_alias}' AND IsActive = true LIMIT 1"
        )
        result = self.sf.query(query)
        records = result.get("records", [])
        if not records:
            raise TaskOptionsError(
                f"User with alias '{user_alias}' not found or inactive"
            )
        return records[0]["Username"]

    def _apply_updates(self, metadata: MetadataElement) -> None:
        """Apply all configured updates to the metadata element."""

        # String fields
        option_to_metadata = {
            self._to_option_name(f): f for f in ECA_OAUTH_STRING_FIELDS
        }
        for option_name, metadata_field in option_to_metadata.items():
            value = self.options.get(option_name)
            if value is not None:
                value = self._inject_namespace(str(value))
                elem = metadata.find(metadata_field)
                if elem is None:
                    elem = metadata.append(metadata_field)
                elem.text = value

        # Boolean fields
        for field in ECA_OAUTH_BOOLEAN_FIELDS:
            option_name = self._to_option_name(field)
            value = self.options.get(option_name)
            if value is not None:
                bool_val = process_bool_arg(value)
                elem = metadata.find(field)
                if elem is None:
                    elem = metadata.append(field)
                elem.text = "true" if bool_val else "false"

        # User reference fields - resolve alias to username
        for metadata_field, alias_option in ECA_OAUTH_USER_FIELDS.items():
            user_alias = self.options.get(alias_option)
            if user_alias:
                username = self._get_username_by_alias(user_alias)
                elem = metadata.find(metadata_field)
                if elem is None:
                    elem = metadata.append(metadata_field)
                elem.text = username

    def _transform_entity(self, metadata: MetadataElement, api_name: str):
        self._apply_updates(metadata)
        return metadata
