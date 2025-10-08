# Quick Start: Update External Credential Task

## Quick Examples

### 1. Update Auth Header (Simple)

```yaml
# In cumulusci.yml
tasks:
    update_api_credential:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyAPICredential
            parameters:
                - auth_header:
                      name: "Authorization"
                      value: "Bearer my-token-123"
                      secret: true
```

Run:

```bash
cci task run update_api_credential --org dev
```

### 2. Update with Environment Variable (Recommended for Secrets)

```yaml
# In cumulusci.yml
tasks:
    update_api_credential_secure:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MyAPICredential
            transform_parameters:
                - auth_header:
                      name: "Authorization"
                      value: "API_TOKEN" # Reads from $API_TOKEN
                      secret: true # Hides value in logs
```

Run:

```bash
export API_TOKEN="Bearer secret-token-456"
cci task run update_api_credential_secure --org dev
```

### 3. Update with OAuth Credentials

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
```

### 4. Update Multiple Parameters

```yaml
tasks:
    update_multi_credential:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: MultiCredential
            parameters:
                - auth_provider: "MyAuthProvider"
                - auth_provider_url: "https://auth.example.com/oauth2/authorize"
                - jwt_body_claim:
                      name: "sub"
                      value: '{"sub":"user123","aud":"production"}'
```

### 5. Command Line (One-off Update)

```bash
cci task run update_external_credential \
    --org dev \
    -o name "MyExternalCredential" \
    -o parameters '[{"auth_header": {"name": "Authorization", "value": "Bearer token123", "secret": true}}]'
```

### 6. In a Flow (Automated Deployment)

```yaml
flows:
    deploy_with_config:
        steps:
            1:
                task: deploy
            2:
                task: update_external_credential
                options:
                    name: ProductionAPI
                    transform_parameters:
                        - auth_header:
                              name: "Authorization"
                              value: "PROD_API_TOKEN"
                              secret: true
```

## Available Parameter Types

Choose ONE per parameter:

| Parameter Type                      | Object Type        | Description                            | 2GP Subscriber Editable |
| ----------------------------------- | ------------------ | -------------------------------------- | ----------------------- |
| `auth_header`                       | HttpHeader         | Authorization header with name/value   | No                      |
| `auth_provider`                     | str                | Auth provider name                     | **Yes**                 |
| `auth_provider_url`                 | str                | Auth provider URL                      | No                      |
| `auth_provider_url_query_parameter` | ExtParameter       | URL query parameter with name/value    | No                      |
| `auth_parameter`                    | ExtParameter       | Auth parameter with name/value         | No                      |
| `jwt_body_claim`                    | ExtParameter       | JWT body claim with name/value         | No                      |
| `jwt_header_claim`                  | ExtParameter       | JWT header claim with name/value       | No                      |
| `named_principal`                   | ExternalCredential | Named principal with OAuth credentials | No                      |
| `per_user_principal`                | str                | Per user principal                     | No                      |
| `signing_certificate`               | str                | Signing certificate                    | **Yes**                 |

## Object Structures

### HttpHeader

-   `name` (str): Header name (required)
-   `value` (str): Header value (required)
-   `group` (str): Parameter group (optional)
-   `sequence_number` (int): Order of execution (optional)
-   `secret` (bool): Hide value in logs (optional, default: false)

### ExtParameter

-   `name` (str): Parameter name (required)
-   `value` (str): Parameter value (required)
-   `group` (str): Parameter group (optional)
-   `sequence_number` (int): Order of execution (optional)

### ExternalCredential (Named Principal)

-   `name` (str): Principal name (required)
-   `value` (str): Optional value
-   `client_id` (str): OAuth client ID (optional)
-   `client_secret` (str): OAuth client secret (optional)
-   `auth_protocol` (str): Authentication protocol (optional, default: "OAuth")
-   `group` (str): Parameter group (optional)
-   `sequence_number` (int): Order of execution (optional)
-   `secret` (bool): Hide value in logs (optional, default: false)

## Common Use Cases

### Use Case 1: Update API Token After Deployment

```yaml
flows:
    deploy_to_prod:
        steps:
            1:
                task: deploy
            2:
                task: update_external_credential
                options:
                    name: ProductionAPI
                    transform_parameters:
                        - auth_header: "PROD_API_TOKEN"
                          secret: true
```

### Use Case 2: Configure OAuth Provider

```yaml
tasks:
    configure_oauth:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: OAuthCredential
            parameters:
                - auth_provider: "GoogleOAuth"
                - auth_provider_url: "https://accounts.google.com/o/oauth2/v2/auth"
```

### Use Case 3: Update JWT Claims

```yaml
tasks:
    update_jwt:
        class_path: cumulusci.tasks.salesforce.update_external_credential.UpdateExternalCredential
        options:
            name: JWTCredential
            parameters:
                - jwt_body_claim: '{"iss":"myapp","sub":"api-user","aud":"production"}'
                - jwt_header_claim: '{"alg":"RS256","typ":"JWT"}'
```

## Tips & Best Practices

1. **Always use `transform_parameters` for secrets** - Don't hardcode tokens in YAML
2. **Set `secret: true`** for sensitive values to mask them in logs
3. **Use descriptive parameter names** when adding new parameters
4. **Test in scratch org first** before deploying to production
5. **Check 2GP manageability** - Some parameters can only be updated by subscribers

## Troubleshooting

### Error: "External credential 'X' not found"

-   Check the DeveloperName is correct (case-sensitive)
-   Verify the credential exists in the target org
-   If namespaced, add `namespace: "yourns"` option

### Error: "At least one parameter must be provided"

-   Each parameter object must have at least one parameter type field
-   Check your YAML syntax

### Error: "Failed to update external credential object"

-   Check org permissions (user needs access to Tooling API)
-   Verify the parameter types are valid
-   Check Salesforce API version compatibility

## Testing

Run the test suite:

```bash
cd /path/to/CumulusCI
pytest cumulusci/tasks/salesforce/tests/test_update_external_credential.py -v
```

## Documentation

Full documentation: `docs/update_external_credential.md`

## Support

For issues or questions:

1. Check the full documentation
2. Review test cases for examples
3. Compare with `update_named_credential` task (similar pattern)
