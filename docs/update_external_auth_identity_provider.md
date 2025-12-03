# Update External Auth Identity Provider Task

## Overview

The `update_external_auth_identity_provider` task allows you to update External Auth Identity Provider parameters and credentials in a Salesforce org using the Tooling API and Connect API. This task is useful for managing OAuth and OpenID Connect identity providers in your Salesforce org.

## Task Class

`cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider`

## References

-   [Tooling API - ExternalAuthIdentityProvider](https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/tooling_api_objects_externalauthidentityprovider.htm)
-   [Connect API - External Auth Identity Provider Credentials](https://developer.salesforce.com/docs/atlas.en-us.chatterapi.meta/chatterapi/connect_resources_named_credentials_external_auth_identity_provider_credentials.htm)

## Options

### Required Options

-   `name` (str): Name of the external auth identity provider to update (DeveloperName)

### Optional Options

-   `namespace` (str): Namespace of the external auth identity provider to update. Default: empty string (for unmanaged or current namespace)
-   `parameters` (list): List of parameter objects to update. Default: empty list
-   `transform_parameters` (list): List of parameter objects to transform from environment variables. Default: empty list

## External Auth Identity Provider Parameters

Each parameter in the `parameters` or `transform_parameters` list can include the following fields:

### Parameter Types (one required per parameter)

-   `authorize_url` (str): The authorization endpoint URL
-   `token_url` (str): The token endpoint URL
-   `user_info_url` (str): The user info endpoint URL
-   `jwks_url` (str): The JWKS (JSON Web Key Set) endpoint URL for OpenID Connect
-   `issuer_url` (str): The issuer URL for OpenID Connect
-   `client_authentication` (str): The client authentication method (e.g., ClientSecretBasic, ClientSecretPost, ClientSecretJwt)
-   `custom_parameter` (ExtParameter): Custom parameter with name and value
-   `identity_provider_option` (ExtParameter): Identity provider option with name and value (e.g., PkceEnabled, UserinfoEnabled)
-   `credential` (ExternalAuthIdentityProviderCredential): Credential to update with client ID and secret

### Parameter Object Structures

#### ExtParameter

```yaml
custom_parameter:
    name: "scope" # Parameter name
    value: "openid profile email" # Parameter value
    sequence_number: 1 # Optional sequence number
```

#### ExternalAuthIdentityProviderCredential

```yaml
credential:
    name: "MyCredential" # Credential name
    client_id: "my-client-id" # OAuth client ID
    client_secret: "my-client-secret" # OAuth client secret
    auth_protocol: "OAuth" # Authentication protocol (default: OAuth)
```

### Additional Options

-   `secret` (bool): Whether the parameter value is a secret (for logging purposes). Default: False

## Parameter Validation

-   Each parameter object must have exactly one of the parameter types specified
-   The task will fail if no parameters or multiple parameter types are provided

## Environment Variable Transformation

When using `transform_parameters`, parameter values are treated as environment variable names and will be resolved at runtime:

```yaml
transform_parameters:
    - authorize_url: "AUTH_PROVIDER_AUTHORIZE_URL" # Will be resolved from env var
    - credential:
          name: "MyCredential"
          client_id: "OAUTH_CLIENT_ID" # Will be resolved from env var
          client_secret: "OAUTH_CLIENT_SECRET" # Will be resolved from env var
```

## Usage Examples

### Example 1: Update Authorization and Token URLs

```yaml
tasks:
    update_cognito_auth:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: CognitoAuth
            parameters:
                - authorize_url: "https://auth.example.com/oauth2/authorize"
                - token_url: "https://auth.example.com/oauth2/token"
```

### Example 2: Update Credentials with Client ID and Secret

```yaml
tasks:
    update_auth_credentials:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            parameters:
                - credential:
                      name: "ProductionCredential"
                      client_id: "abc123xyz"
                      client_secret: "supersecret456"
                      auth_protocol: "OAuth"
```

### Example 3: Update Using Environment Variables

```yaml
tasks:
    update_auth_from_env:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            transform_parameters:
                - authorize_url: "AUTH_AUTHORIZE_URL"
                - token_url: "AUTH_TOKEN_URL"
                - user_info_url: "AUTH_USERINFO_URL"
                - credential:
                      name: "EnvCredential"
                      client_id: "OAUTH_CLIENT_ID"
                      client_secret: "OAUTH_CLIENT_SECRET"
```

### Example 4: Update OpenID Connect Provider

```yaml
tasks:
    update_oidc_provider:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: OpenIDProvider
            parameters:
                - issuer_url: "https://auth.example.com"
                - jwks_url: "https://auth.example.com/.well-known/jwks.json"
                - identity_provider_option:
                      name: "PkceEnabled"
                      value: "true"
```

### Example 5: Update Client Authentication Method

```yaml
tasks:
    update_client_auth:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            parameters:
                - client_authentication: "ClientSecretBasic"
```

### Example 6: Update Namespaced Provider

```yaml
tasks:
    update_namespaced_provider:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            namespace: myns
            parameters:
                - authorize_url: "https://auth.example.com/authorize"
```

### Example 7: Update Custom Parameters

```yaml
tasks:
    update_custom_params:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            parameters:
                - custom_parameter:
                      name: "scope"
                      value: "openid profile email"
                      sequence_number: 1
```

## Using in Flows

```yaml
flows:
    deploy_with_auth_provider:
        steps:
            1:
                task: deploy
            2:
                task: update_external_auth_identity_provider
                options:
                    name: MyAuthProvider
                    transform_parameters:
                        - authorize_url: "AUTH_AUTHORIZE_URL"
                        - token_url: "AUTH_TOKEN_URL"
                        - credential:
                              name: "APICredential"
                              client_id: "API_CLIENT_ID"
                              client_secret: "API_CLIENT_SECRET"
```

## Command Line Usage

```bash
# Update with direct values
cci task run update_external_auth_identity_provider \
    --org dev \
    -o name "MyAuthProvider" \
    -o parameters '[{"authorize_url": "https://auth.example.com/authorize"}]'

# Update with environment variables
export AUTH_AUTHORIZE_URL="https://auth.example.com/authorize"
export AUTH_TOKEN_URL="https://auth.example.com/token"
export OAUTH_CLIENT_ID="my-client-id"
export OAUTH_CLIENT_SECRET="my-client-secret"

cci task run update_external_auth_identity_provider \
    --org dev \
    -o name "MyAuthProvider" \
    -o transform_parameters '[{"authorize_url": "AUTH_AUTHORIZE_URL"}, {"token_url": "AUTH_TOKEN_URL"}, {"credential": {"name": "MyCredential", "client_id": "OAUTH_CLIENT_ID", "client_secret": "OAUTH_CLIENT_SECRET"}}]'
```

## Notes

-   The task uses the Tooling API to update External Auth Identity Provider parameters
-   The task uses the Connect API to update credentials (client ID and secret)
-   Parameters are matched by type and name, allowing both updates and additions
-   When updating credentials, the task will POST if no credentials exist, or PUT to update existing credentials
-   The task logs parameter updates while masking secret values for security
-   The task supports namespace prefixes for managed packages

## Error Handling

The task will raise `SalesforceDXException` in the following cases:

-   External auth identity provider not found with the specified name
-   Failed to retrieve the external auth identity provider object
-   Failed to update the external auth identity provider object
-   Failed to update credentials

## Best Practices

1. **Use Environment Variables for Secrets**: Always use `transform_parameters` for sensitive values like client secrets
2. **Test in Scratch Orgs First**: Test the task in a scratch org before running against production
3. **Document Parameter Changes**: Keep track of which parameters are being updated and why
4. **Namespace Awareness**: Be explicit about namespaces when working with managed packages
5. **Credential Updates**: Update credentials separately from other parameters for better control

## Common Use Cases

### Setting Up OAuth for External API Integration

```yaml
tasks:
    setup_oauth_provider:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: ExternalAPIAuth
            transform_parameters:
                - authorize_url: "API_AUTHORIZE_URL"
                - token_url: "API_TOKEN_URL"
                - user_info_url: "API_USERINFO_URL"
                - credential:
                      name: "APICredential"
                      client_id: "API_CLIENT_ID"
                      client_secret: "API_CLIENT_SECRET"
```

### Updating Existing Provider URLs After Environment Change

```yaml
tasks:
    update_provider_urls:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            parameters:
                - authorize_url: "https://new-auth.example.com/authorize"
                - token_url: "https://new-auth.example.com/token"
```

### Enabling PKCE for Security

```yaml
tasks:
    enable_pkce:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            parameters:
                - identity_provider_option:
                      name: "PkceEnabled"
                      value: "true"
```

# Update External Auth Identity Provider Task - Implementation Summary

## Overview

A new CumulusCI task has been created to update External Auth Identity Provider parameters and credentials in Salesforce orgs using the Tooling API and Connect API. This task follows the same pattern as the existing `update_named_credential` and `update_external_credential` tasks.

## Files Created

### 1. Main Task Implementation

**File:** `cumulusci/tasks/salesforce/update_external_auth_identity_provider.py`

**Key Components:**

-   `ExtParameter` - Pydantic model for parameter configuration
-   `ExternalAuthIdentityProviderCredential` - Pydantic model for credential configuration
-   `ExternalAuthIdentityProviderParameter` - Pydantic model for parameter configuration
-   `TransformExternalAuthIdentityProviderParameter` - Supports reading values from environment variables
-   `UpdateExternalAuthIdentityProvider` - Main task class that extends `BaseSalesforceApiTask`

**Supported Parameters:**

-   AuthorizeUrl - The authorization endpoint URL
-   TokenUrl - The token endpoint URL
-   UserInfoUrl - The user info endpoint URL
-   JwksUrl - The JWKS endpoint URL (for OpenID Connect)
-   IssuerUrl - The issuer URL (for OpenID Connect)
-   ClientAuthentication - Client authentication method
-   CustomParameter - Custom parameters with name and value
-   IdentityProviderOptions - Identity provider options (e.g., PkceEnabled)
-   Credential - OAuth client ID and secret

### 2. Comprehensive Test Suite

**File:** `cumulusci/tasks/salesforce/tests/test_update_external_auth_identity_provider.py`

**Test Coverage:**

-   26 test cases covering:
    -   Parameter model validation
    -   Credential model validation
    -   Environment variable transformation
    -   Successful updates
    -   Error handling (not found, retrieve errors, update errors)
    -   Namespace support
    -   Multiple parameters
    -   Adding new parameters
    -   Credential updates
    -   Transform parameters

### 3. Task Registration

**File:** `cumulusci/cumulusci.yml`

Added task registration:

```yaml
update_external_auth_identity_provider:
    class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
    description: Update external auth identity provider parameters and credentials
    group: Metadata Transformations
```

### 4. Documentation

**File:** `docs/update_external_auth_identity_provider.md`

Comprehensive documentation including:

-   Task overview and options
-   Parameter types and fields
-   7 usage examples
-   Command line usage
-   Error handling
-   Best practices
-   Common use cases

## Task Features

### Parameter Management

-   **URL Configuration**: Update authorization, token, user info, JWKS, and issuer URLs
-   **Authentication Methods**: Configure client authentication methods (ClientSecretBasic, ClientSecretPost, etc.)
-   **Custom Parameters**: Add custom parameters with sequence numbers
-   **Identity Provider Options**: Configure options like PKCE enablement
-   **Credential Management**: Update OAuth client ID and secret via Connect API

### Environment Variable Support

-   All parameter values can be resolved from environment variables using `transform_parameters`
-   Credentials (client ID and secret) support environment variable resolution
-   Secret values are masked in logs for security

### API Integration

-   **Tooling API**: Used to query and update External Auth Identity Provider metadata
-   **Connect API**: Used to update credentials (client ID and secret)
-   Supports both POST (create) and PUT (update) operations for credentials

### Error Handling

-   Validates that exactly one parameter type is specified per parameter object
-   Provides clear error messages for common issues
-   Handles namespace prefixes for managed packages
-   Gracefully handles missing or invalid credentials

## Usage Patterns

### Basic URL Update

```yaml
tasks:
    update_auth_urls:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            parameters:
                - authorize_url: "https://auth.example.com/authorize"
                - token_url: "https://auth.example.com/token"
```

### Credential Update with Environment Variables

```yaml
tasks:
    update_credentials:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: MyAuthProvider
            transform_parameters:
                - credential:
                      name: "APICredential"
                      client_id: "OAUTH_CLIENT_ID"
                      client_secret: "OAUTH_CLIENT_SECRET"
```

### OpenID Connect Configuration

```yaml
tasks:
    configure_oidc:
        class_path: cumulusci.tasks.salesforce.update_external_auth_identity_provider.UpdateExternalAuthIdentityProvider
        options:
            name: OpenIDProvider
            parameters:
                - issuer_url: "https://auth.example.com"
                - jwks_url: "https://auth.example.com/.well-known/jwks.json"
                - identity_provider_option:
                      name: "PkceEnabled"
                      value: "true"
```

## Technical Details

### Tooling API Query

```sql
SELECT Id 
FROM ExternalAuthIdentityProvider 
WHERE DeveloperName='MyAuthProvider' 
AND NamespacePrefix='myns' 
LIMIT 1
```

### Tooling API Metadata Structure

```json
{
    "Metadata": {
        "externalAuthIdentityProviderParameters": [
            {
                "parameterType": "AuthorizeUrl",
                "parameterName": "AuthorizeUrl",
                "parameterValue": "https://auth.example.com/authorize",
                "sequenceNumber": null,
                "description": null
            }
        ]
    }
}
```

### Connect API Credential Structure

```json
{
    "externalAuthIdentityProvider": "MyAuthProvider",
    "authenticationProtocol": "OAuth",
    "credentials": {
        "clientId": {
            "encrypted": false,
            "value": "my-client-id"
        },
        "clientSecret": {
            "encrypted": true,
            "value": "my-client-secret"
        }
    }
}
```

## Comparison with Related Tasks

| Feature                      | update_named_credential | update_external_credential | update_external_auth_identity_provider |
| ---------------------------- | ----------------------- | -------------------------- | -------------------------------------- |
| Object Type                  | NamedCredential         | ExternalCredential         | ExternalAuthIdentityProvider           |
| Tooling API                  | ✓                       | ✓                          | ✓                                      |
| Connect API                  | ✗                       | ✓                          | ✓                                      |
| OAuth Credentials            | ✗                       | ✓                          | ✓                                      |
| URL Configuration            | ✓                       | ✗                          | ✓                                      |
| Custom Parameters            | ✗                       | ✓                          | ✓                                      |
| Environment Variable Support | ✓                       | ✓                          | ✓                                      |

## Integration with CumulusCI Flows

The task can be integrated into CumulusCI flows for automated deployments:

```yaml
flows:
    deploy_with_auth:
        steps:
            1:
                task: deploy
            2:
                task: update_external_auth_identity_provider
                options:
                    name: MyAuthProvider
                    transform_parameters:
                        - authorize_url: "AUTH_AUTHORIZE_URL"
                        - token_url: "AUTH_TOKEN_URL"
                        - credential:
                              name: "APICredential"
                              client_id: "OAUTH_CLIENT_ID"
                              client_secret: "OAUTH_CLIENT_SECRET"
```

## Best Practices

1. **Use Environment Variables**: Store sensitive values like client secrets in environment variables
2. **Test in Scratch Orgs**: Always test in a scratch org before running against production
3. **Namespace Awareness**: Be explicit about namespaces when working with managed packages
4. **Separate Updates**: Consider separating URL updates from credential updates for better control
5. **Error Handling**: Implement proper error handling in your flows
6. **Documentation**: Document which parameters are being updated and why

## References

-   [Tooling API - ExternalAuthIdentityProvider](https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/tooling_api_objects_externalauthidentityprovider.htm)
-   [Connect API - External Auth Identity Provider Credentials](https://developer.salesforce.com/docs/atlas.en-us.chatterapi.meta/chatterapi/connect_resources_named_credentials_external_auth_identity_provider_credentials.htm)

## Future Enhancements

Potential enhancements for future versions:

-   Support for additional authentication protocols
-   Bulk parameter updates
-   Validation of URL formats
-   Support for certificate-based authentication
-   Enhanced logging and reporting

