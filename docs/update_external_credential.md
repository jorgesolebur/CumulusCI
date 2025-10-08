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
-   `auth_provider` (str): Auth provider name (only subscriber editable in 2GP)
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
