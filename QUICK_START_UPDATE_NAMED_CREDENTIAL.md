# Quick Start: Update Named Credential Task

## Quick Examples

### 1. Update URL (Simple)

```yaml
# In cumulusci.yml
tasks:
    update_api_endpoint:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyAPICredential
            parameters:
                - url: "https://api.example.com/v2/endpoint"
```

Run:

```bash
cci task run update_api_endpoint --org dev
```

### 2. Update with Environment Variable (Recommended for Secrets)

```yaml
# In cumulusci.yml
tasks:
    update_api_secure:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyAPICredential
            transform_parameters:
                - url: "API_ENDPOINT_URL" # Reads from $API_ENDPOINT_URL env var
```

Run:

```bash
export API_ENDPOINT_URL="https://api.production.com/v2/endpoint"
cci task run update_api_secure --org dev
```

### 3. Update with HTTP Headers

```yaml
tasks:
    update_with_headers:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyAPICredential
            parameters:
                - url: "https://api.example.com/endpoint"
                - http_header:
                      - name: "Authorization"
                        value: "Bearer token123"
                        secret: true
                        sequence_number: 1
                      - name: "X-API-Version"
                        value: "2023-10-01"
                        sequence_number: 2
```

### 4. Update with Authentication

```yaml
tasks:
    update_auth_credential:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: AuthCredential
            parameters:
                - authentication: "MyExternalCredential"
```

### 5. Update with Callout Options

```yaml
tasks:
    update_callout_options:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyAPICredential
            callout_options:
                allow_merge_fields_in_body: true
                allow_merge_fields_in_header: true
                generate_authorization_header: true
            parameters:
                - url: "https://api.example.com/endpoint"
```

### 6. Command Line (One-off Update)

```bash
cci task run update_named_credential \
    --org dev \
    -o name "MyNamedCredential" \
    -o parameters '[{"url": "https://api.example.com/v2/endpoint"}]'
```

### 7. In a Flow (Automated Deployment)

```yaml
flows:
    deploy_with_config:
        steps:
            1:
                task: deploy
            2:
                task: update_named_credential
                options:
                    name: ProductionAPI
                    transform_parameters:
                        - url: "PROD_API_ENDPOINT"
                        - http_header:
                              - name: "Authorization"
                                value: "PROD_API_TOKEN"
                                secret: true
```

## Available Parameter Types

Choose ONE per parameter:

| Parameter Type                       | Data Type | Description                           | 2GP Subscriber Editable |
| ------------------------------------ | --------- | ------------------------------------- | ----------------------- |
| `url`                                | str       | Endpoint URL for the named credential | **Yes**                 |
| `authentication`                     | str       | External credential reference         | **Yes**                 |
| `certificate`                        | str       | Client certificate for authentication | **Yes**                 |
| `allowed_managed_package_namespaces` | str       | Allowed managed package namespaces    | **Yes**                 |
| `http_header`                        | list      | HTTP headers with name/value pairs    | **Yes**                 |

## Object Structures

### HttpHeader

-   `name` (str): Header name (required)
-   `value` (str): Header value (required)
-   `sequence_number` (int): Order of execution (optional)
-   `secret` (bool): Hide value in logs (optional, default: false)

### Callout Options

-   `allow_merge_fields_in_body` (bool): Allow merge fields in request body
-   `allow_merge_fields_in_header` (bool): Allow merge fields in headers
-   `generate_authorization_header` (bool): Generate authorization header

## Common Use Cases

### Use Case 1: Update API Endpoint After Deployment

```yaml
flows:
    deploy_to_prod:
        steps:
            1:
                task: deploy
            2:
                task: update_named_credential
                options:
                    name: ProductionAPI
                    transform_parameters:
                        - url: "PROD_API_ENDPOINT"
```

### Use Case 2: Configure Authentication

```yaml
tasks:
    configure_auth:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: AuthCredential
            parameters:
                - authentication: "MyExternalCredential"
```

### Use Case 3: Update API Headers

```yaml
tasks:
    update_headers:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyAPICredential
            parameters:
                - http_header:
                      - name: "Authorization"
                        value: "Bearer new-token"
                        secret: true
                      - name: "X-API-Version"
                        value: "2023-10-01"
```

## Tips & Best Practices

1. **Always use `transform_parameters` for secrets** - Don't hardcode tokens in YAML
2. **Set `secret: true`** for sensitive values to mask them in logs
3. **Use descriptive header names** when adding new headers
4. **Test in scratch org first** before deploying to production
5. **Only works with SecuredEndpoint** - Other named credential types are not supported
6. **Use sequence numbers** to control header order

## Troubleshooting

### Error: "Named credential 'X' not found"

-   Check the DeveloperName is correct (case-sensitive)
-   Verify the credential exists in the target org
-   If namespaced, add `namespace: "yourns"` option

### Error: "Only one of the parameters is required"

-   Each parameter object must have exactly one parameter type field
-   Check your YAML syntax

### Error: "Named credential 'X' is not a secured endpoint"

-   Only SecuredEndpoint named credentials are supported
-   Check the named credential type in Salesforce Setup

### Error: "Failed to update named credential object"

-   Check org permissions (user needs access to Tooling API)
-   Verify the parameter types are valid
-   Check Salesforce API version compatibility

## Testing

Run the test suite:

```bash
cd /path/to/CumulusCI
pytest cumulusci/tasks/salesforce/tests/test_update_named_credential.py -v
```

## Documentation

Full documentation: `docs/update_named_credential.md`

## Support

For issues or questions:

1. Check the full documentation
2. Review test cases for examples
3. Compare with `update_external_credential` task (similar pattern)
