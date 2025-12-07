# Update External Credential Task

## Overview

The `update_external_credential` task allows you to update External Credential parameters in a Salesforce org using the Tooling API. This task is designed to work with the manageability rules of External Credentials in Second-Generation Packages (2GP).

## Task Class

`cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential`

## Options

### Required Options

-   `name` (str): Name of the external credential to update (DeveloperName)

### Optional Options

-   `namespace` (str): Namespace of the external credential to update. Default: empty string (for unmanaged or current namespace)
-   `description` (str): Description of the external credential. Default: None
-   `parameters` (list): List of parameter objects to update. Default: empty list
-   `transform_parameters` (list): List of parameter objects to transform from environment variables. Default: empty list

## External Credential Parameters

Each parameter in the `parameters` or `transform_parameters` list can include the following fields:

### Parameter Types (one required per parameter)

-   `auth_header` (HttpHeader): Auth header with name, value, and optional metadata
-   `auth_provider` (str): Auth provider name (only subscriber editable in 2GP) - **Mutually exclusive with `external_auth_identity_provider`**
-   `external_auth_identity_provider` (str): External auth identity provider name - **Mutually exclusive with `auth_provider`**
-   `auth_provider_url` (str): Auth provider URL
-   `auth_provider_url_query_parameter` (ExtParameter): Auth provider URL query parameter with name and value
-   `auth_parameter` (ExtParameter): Auth parameter with name and value
-   `jwt_body_claim` (ExtParameter): JWT body claim with name and value
-   `jwt_header_claim` (ExtParameter): JWT header claim with name and value
-   `named_principal` (ExternalCredential): Named principal with OAuth credentials
-   `per_user_principal` (str): Per user principal
-   `signing_certificate` (str): Signing certificate (only subscriber editable in 2GP)

### Parameter Object Structures

#### HttpHeader

```yaml
auth_header:
    name: "Authorization" # Header name
    value: "Bearer token123" # Header value
    group: "DefaultGroup" # Optional parameter group
    sequence_number: 1 # Optional sequence number
    secret: true # Optional secret flag
```

#### ExtParameter

```yaml
jwt_body_claim:
    name: "sub" # Parameter name
    value: '{"sub":"user123"}' # Parameter value
    group: "JWTClaims" # Optional parameter group
    sequence_number: 1 # Optional sequence number
```

#### ExternalCredential (Named Principal)

```yaml
named_principal:
    name: "MyPrincipal" # Principal name
    value: "test-value" # Optional value
    client_id: "client123" # OAuth client ID
    client_secret: "secret456" # OAuth client secret
    auth_protocol: "OAuth2" # Authentication protocol (default: OAuth)
    group: "OAuthGroup" # Optional parameter group
    sequence_number: 1 # Optional sequence number
    secret: true # Optional secret flag
```

### Optional Parameter Fields

-   `secret` (bool): Whether the value is a secret (affects logging only). Default: False

## Usage Examples

### Example 1: Update Auth Header

```yaml
tasks:
    update_my_external_credential:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyExternalCredential
            parameters:
                - auth_header:
                      name: "Authorization"
                      value: "Bearer my-new-token-123"
                      secret: true
```

### Example 2: Update Multiple Parameters

```yaml
tasks:
    update_external_cred_multi:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyAPICredential
            parameters:
                - auth_header:
                      name: "Authorization"
                      value: "Bearer production-token"
                      sequence_number: 1
                      secret: true
                - jwt_body_claim:
                      name: "sub"
                      value: '{"sub":"api-user","aud":"production"}'
                      sequence_number: 2
```

### Example 3: Update with Named Principal (OAuth)

```yaml
tasks:
    update_oauth_credential:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: OAuthCredential
            parameters:
                - named_principal:
                      name: "MyOAuthPrincipal"
                      client_id: "client123"
                      client_secret: "secret456"
                      auth_protocol: "OAuth2"
                      sequence_number: 1
```

### Example 4: Update with Environment Variables

Use `transform_parameters` to read values from environment variables:

```yaml
tasks:
    update_external_cred_env:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyExternalCredential
            transform_parameters:
                - auth_header:
                      name: "Authorization"
                      value: "MY_AUTH_TOKEN" # Reads from $MY_AUTH_TOKEN env var
                      secret: true
                - named_principal:
                      name: "OAuthPrincipal"
                      client_id: "CLIENT_ID"
                      client_secret: "CLIENT_SECRET"
```

### Example 5: Update Namespaced External Credential

```yaml
tasks:
    update_namespaced_cred:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyExternalCredential
            namespace: myns
            parameters:
                - auth_provider: "MyAuthProvider"
```

### Example 6: Update Auth Provider URL

```yaml
tasks:
    update_auth_provider_url:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: OAuthCredential
            parameters:
                - auth_provider_url: "https://auth.example.com/oauth2/authorize"
```

### Example 7: Update JWT Claims

```yaml
tasks:
    update_jwt_claims:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: JWTCredential
            parameters:
                - jwt_body_claim:
                      name: "sub"
                      value: '{"iss":"myapp","sub":"api-user","aud":"production"}'
                - jwt_header_claim:
                      name: "alg"
                      value: '{"alg":"RS256","typ":"JWT"}'
```

### Example 8: Update with External Auth Identity Provider

```yaml
tasks:
    update_external_auth:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: CognitoCredential
            parameters:
                - external_auth_identity_provider: "MyExternalAuthProvider"
```

**Note:** Adding an `external_auth_identity_provider` will automatically remove any existing `auth_provider` parameters due to mutual exclusivity.

## Using in Flows

```yaml
flows:
    deploy_with_credentials:
        steps:
            1:
                task: deploy
            2:
                task: update_external_credential
                options:
                    name: MyAPICredential
                    transform_parameters:
                        - auth_header: "API_TOKEN"
                        - auth_provider: "AUTH_PROVIDER_NAME"
```

## Command Line Usage

```bash
# Update with direct values
cci task run update_external_credential \
    --org dev \
    -o name "MyExternalCredential" \
    -o parameters '[{"auth_header": {"name": "Authorization", "value": "Bearer token123", "secret": true}}]'

# Update with OAuth credentials
cci task run update_external_credential \
    --org dev \
    -o name "OAuthCredential" \
    -o parameters '[{"named_principal": {"name": "MyPrincipal", "client_id": "client123", "client_secret": "secret456", "auth_protocol": "OAuth2"}}]'

# Update with environment variables
export MY_AUTH_TOKEN="Bearer secret-token-456"
cci task run update_external_credential \
    --org dev \
    -o name "MyExternalCredential" \
    -o transform_parameters '[{"auth_header": {"name": "Authorization", "value": "MY_AUTH_TOKEN", "secret": true}}]'
```

## Behavior

### Parameter Matching

The task matches existing parameters based on:

-   `parameterType`
-   `parameterName` (if specified)
-   `sequenceNumber` (if specified)

If a matching parameter is found, it will be updated. If not found, a new parameter will be added.

### AuthProvider and ExternalAuthIdentityProvider Mutual Exclusivity

**Important:** `AuthProvider` and `ExternalAuthIdentityProvider` parameter types are mutually exclusive and cannot coexist in the same External Credential.

When you add or update either of these parameter types:

-   **Adding/Updating `auth_provider`**: Automatically removes all `ExternalAuthIdentityProvider` parameters
-   **Adding/Updating `external_auth_identity_provider`**: Automatically removes all `AuthProvider` parameters

This behavior ensures compliance with Salesforce's requirement that these two authentication methods cannot be used together in a single External Credential.

**Example Scenario:**

```yaml
# Initial state: External Credential has ExternalAuthIdentityProvider
# Current parameters:
#   - ExternalAuthIdentityProvider: "Cognito"
#   - AuthParameter: "scope=openid"

# Update with AuthProvider
tasks:
    update_to_auth_provider:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyExternalCredential
            parameters:
                - auth_provider: "MyAuthProvider"

# Result: 
#   - AuthProvider: "MyAuthProvider" (new)
#   - AuthParameter: "scope=openid" (preserved)
#   - ExternalAuthIdentityProvider: removed automatically
```

The task logs the number of conflicting parameters removed for transparency.

### Template Parameters

When adding new parameters, the task uses the first existing parameter as a template to maintain consistent structure. If no existing parameters are found, it uses a default template.

### Error Handling

The task will raise a `SalesforceDXException` if:

-   The external credential is not found
-   The external credential object cannot be retrieved
-   The update operation fails

## Manageability in 2GP

According to Salesforce documentation, the following External Credential parameters are **only subscriber editable** in Second-Generation Packages:

-   `auth_provider` (AuthProvider)
-   `signing_certificate` (SigningCertificate)

This means these parameters can be updated by subscribers after package installation, making them ideal for configuration that varies by org.

## Related Documentation

-   [Salesforce External Credentials Documentation](https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_callouts_named_credentials.htm)
-   [2GP Packageable Components](https://developer.salesforce.com/docs/atlas.en-us.pkg2_dev.meta/pkg2_dev/packaging_packageable_components.htm)
-   [CumulusCI Task Documentation](https://cumulusci.readthedocs.io/en/latest/tasks.html)

## Testing

Run the comprehensive test suite:

```bash
pytest cumulusci/tasks/salesforce/tests/test_update_external_credential.py -v
```

## See Also

-   `update_named_credential` - Similar task for updating Named Credentials

# Update External Credential Task - Implementation Summary

## Overview

A new CumulusCI task has been created to update External Credential parameters in Salesforce orgs using the Tooling API. This task follows the same pattern as the existing `update_named_credential` task.

## Files Created

### 1. Main Task Implementation

**File:** `cumulusci/tasks/salesforce/update_external_credential.py`

**Key Components:**

-   `ExternalCredentialParameter` - Pydantic model for parameter configuration
-   `TransformExternalCredentialParameter` - Supports reading values from environment variables
-   `UpdateExternalCredential` - Main task class that extends `BaseSalesforceApiTask`

**Supported Parameters:**

-   AuthHeader
-   AuthProvider (subscriber editable in 2GP) - **Mutually exclusive with ExternalAuthIdentityProvider**
-   ExternalAuthIdentityProvider - **Mutually exclusive with AuthProvider**
-   AuthProviderUrl
-   AuthProviderUrlQueryParameter
-   AuthParameter
-   AwsStsPrincipal
-   JwtBodyClaim
-   JwtHeaderClaim
-   NamedPrincipal
-   PerUserPrincipal
-   SigningCertificate (subscriber editable in 2GP)
-   SequenceNumber
-   Description

### 2. Comprehensive Test Suite

**File:** `cumulusci/tasks/salesforce/tests/test_update_external_credential.py`

**Test Coverage:**

-   28 test cases covering:
    -   Parameter model validation
    -   Environment variable transformation
    -   Successful updates
    -   Error handling (not found, retrieve errors, update errors)
    -   Namespace support
    -   Multiple parameters
    -   Adding new parameters
    -   Sequence numbers
    -   AuthProvider and ExternalAuthIdentityProvider mutual exclusivity
    -   Conflict removal and logging

**Test Results:** All 28 tests passing ✓

### 3. Task Registration

**File:** `cumulusci/cumulusci.yml`

Added task registration:

```yaml
update_external_credential:
    class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
    description: Update external credential parameters
    group: Metadata Transformations
```

### 4. Documentation

**File:** `docs/update_external_credential.md`

Comprehensive documentation including:

-   Task overview and options
-   Parameter types and fields
-   5 usage examples
-   Flow integration examples
-   Command-line usage
-   Behavior explanation
-   2GP manageability notes
-   Related documentation links

## Usage Examples

### Basic Usage

```yaml
tasks:
    update_my_credential:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyExternalCredential
            parameters:
                - auth_header: "Bearer token123"
```

### With Environment Variables

```yaml
tasks:
    update_with_env:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyExternalCredential
            transform_parameters:
                - auth_header: "MY_AUTH_TOKEN"
                  secret: true
```

### Command Line

```bash
cci task run update_external_credential \
    --org dev \
    -o name "MyExternalCredential" \
    -o parameters '[{"auth_header": "Bearer token123"}]'
```

## Key Features

1. **Flexible Parameter Updates**: Supports all External Credential parameter types
2. **Environment Variable Support**: Use `transform_parameters` to read from env vars
3. **Secret Masking**: Mark parameters as secret to hide values in logs
4. **Namespace Support**: Works with namespaced and non-namespaced credentials
5. **Smart Parameter Matching**: Updates existing parameters or adds new ones
6. **Template-Based Creation**: Uses existing parameters as templates for consistency
7. **Comprehensive Error Handling**: Clear error messages for all failure scenarios
8. **2GP Compatibility**: Respects 2GP manageability rules

## Implementation Pattern

The task follows the same architectural pattern as `UpdateNamedCredential`:

1. Query Tooling API to find the External Credential by DeveloperName
2. Retrieve the full External Credential metadata object
3. Update parameters in-memory (add new or update existing)
4. PATCH the updated metadata back to Salesforce
5. Log success or raise appropriate exceptions

## Testing

Run tests:

```bash
cd /Users/rupesh.j/Work/CumulusCI
python -m pytest cumulusci/tasks/salesforce/tests/test_update_external_credential.py -v
```

All 28 tests pass successfully.

## Next Steps

The task is ready to use. To integrate into your project:

1. Ensure you're using the latest version of CumulusCI with this task
2. Add the task to your `cumulusci.yml` flows as needed
3. Configure parameters based on your External Credential requirements
4. Use environment variables for sensitive values

## Related Tasks

-   `update_named_credential` - Updates Named Credential parameters
-   Both tasks follow similar patterns and can be used together in flows

## References

-   [Salesforce External Credentials](https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_callouts_named_credentials.htm)
-   [2GP Packageable Components](https://developer.salesforce.com/docs/atlas.en-us.pkg2_dev.meta/pkg2_dev/packaging_packageable_components.htm)
-   [CumulusCI Tasks](https://cumulusci.readthedocs.io/en/latest/tasks.html)
