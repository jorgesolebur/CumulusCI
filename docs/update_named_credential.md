# Update Named Credential Task

## Overview

The `update_named_credential` task allows you to update Named Credential parameters in a Salesforce org using the Tooling API. This task is designed to work with the manageability rules of Named Credentials in Second-Generation Packages (2GP).

## Task Class

`cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential`

## Options

### Required Options

-   `name` (str): Name of the named credential to update (DeveloperName)

### Optional Options

-   `namespace` (str): Namespace of the named credential to update. Default: empty string (for unmanaged or current namespace)
-   `callout_options` (NamedCredentialCalloutOptions): Callout options for the named credential. Default: None
-   `parameters` (list): List of parameter objects to update. Default: empty list
-   `transform_parameters` (list): List of parameter objects to transform from environment variables. Default: empty list

## Named Credential Parameters

Each parameter in the `parameters` or `transform_parameters` list can include the following fields:

### Parameter Types (one required per parameter)

-   `url` (str): Endpoint URL for the named credential
-   `authentication` (str): External credential reference for authentication
-   `certificate` (str): Client certificate for authentication
-   `allowed_managed_package_namespaces` (str): Allowed managed package namespaces
-   `http_header` (list): List of HTTP headers with name, value, and optional metadata

### Parameter Object Structures

#### HttpHeader

```yaml
http_header:
    - name: "Authorization" # Header name
      value: "Bearer token123" # Header value
      sequence_number: 1 # Optional sequence number
      secret: true # Optional secret flag
```

#### Callout Options

```yaml
callout_options:
    allow_merge_fields_in_body: true # Allow merge fields in request body
    allow_merge_fields_in_header: true # Allow merge fields in headers
    generate_authorization_header: true # Generate authorization header
```

### Optional Parameter Fields

-   `secret` (bool): Whether the value is a secret (affects logging only). Default: False
-   `sequence_number` (int): Order of execution for headers. Default: None

## Usage Examples

### Example 1: Update URL

```yaml
tasks:
    update_my_named_credential:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyNamedCredential
            parameters:
                - url: "https://api.example.com/v2/endpoint"
```

### Example 2: Update Multiple Parameters

```yaml
tasks:
    update_named_cred_multi:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyAPICredential
            parameters:
                - url: "https://api.production.com/v2/endpoint"
                - http_header:
                      - name: "Authorization"
                        value: "Bearer production-token"
                        sequence_number: 1
                        secret: true
                      - name: "X-API-Version"
                        value: "2023-10-01"
                        sequence_number: 2
```

### Example 3: Update with Authentication

```yaml
tasks:
    update_auth_credential:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: AuthCredential
            parameters:
                - authentication: "MyExternalCredential"
```

### Example 4: Update with Environment Variables

Use `transform_parameters` to read values from environment variables:

```yaml
tasks:
    update_named_cred_env:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyNamedCredential
            transform_parameters:
                - url: "API_ENDPOINT_URL" # Reads from $API_ENDPOINT_URL env var
                - http_header:
                      - name: "Authorization"
                        value: "API_TOKEN" # Reads from $API_TOKEN env var
                        secret: true
```

### Example 5: Update Namespaced Named Credential

```yaml
tasks:
    update_namespaced_cred:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyNamedCredential
            namespace: myns
            parameters:
                - url: "https://api.example.com/endpoint"
```

### Example 6: Update with Callout Options

```yaml
tasks:
    update_callout_options:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyNamedCredential
            callout_options:
                allow_merge_fields_in_body: true
                allow_merge_fields_in_header: true
                generate_authorization_header: true
            parameters:
                - url: "https://api.example.com/endpoint"
```

### Example 7: Update with Client Certificate

```yaml
tasks:
    update_cert_credential:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: CertCredential
            parameters:
                - certificate: "MyClientCertificate"
```

## Using in Flows

```yaml
flows:
    deploy_with_credentials:
        steps:
            1:
                task: deploy
            2:
                task: update_named_credential
                options:
                    name: MyAPICredential
                    transform_parameters:
                        - url: "API_ENDPOINT_URL"
                        - http_header:
                              - name: "Authorization"
                                value: "API_TOKEN"
                                secret: true
```

## Command Line Usage

```bash
# Update with direct values
cci task run update_named_credential \
    --org dev \
    -o name "MyNamedCredential" \
    -o parameters '[{"url": "https://api.example.com/v2/endpoint"}]'

# Update with HTTP headers
cci task run update_named_credential \
    --org dev \
    -o name "MyNamedCredential" \
    -o parameters '[{"http_header": [{"name": "Authorization", "value": "Bearer token123", "secret": true}]}]'

# Update with environment variables
export API_ENDPOINT_URL="https://api.example.com/endpoint"
cci task run update_named_credential \
    --org dev \
    -o name "MyNamedCredential" \
    -o transform_parameters '[{"url": "API_ENDPOINT_URL"}]'
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

### Secured Endpoint Validation

The task only works with Named Credentials of type "SecuredEndpoint". If the named credential is not a secured endpoint, the task will raise an error.

### Error Handling

The task will raise a `SalesforceDXException` if:

-   The named credential is not found
-   The named credential is not a secured endpoint
-   The named credential object cannot be retrieved
-   The update operation fails

## Manageability in 2GP

Named Credentials in Second-Generation Packages have specific manageability rules:

-   **URL parameters**: Can be updated by subscribers
-   **HTTP headers**: Can be updated by subscribers
-   **Authentication references**: Can be updated by subscribers
-   **Callout options**: Can be updated by subscribers

This makes Named Credentials ideal for configuration that varies by org, such as API endpoints and authentication tokens.

## Related Documentation

-   [Salesforce Named Credentials Documentation](https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_callouts_named_credentials.htm)
-   [2GP Packageable Components](https://developer.salesforce.com/docs/atlas.en-us.pkg2_dev.meta/pkg2_dev/packaging_packageable_components.htm)
-   [CumulusCI Task Documentation](https://cumulusci.readthedocs.io/en/latest/tasks.html)

## Testing

Run the comprehensive test suite:

```bash
pytest cumulusci/tasks/salesforce/tests/test_update_named_credential.py -v
```

## See Also

-   `update_external_credential` - Similar task for updating External Credentials
