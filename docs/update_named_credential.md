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

# Update Named Credential Task - Implementation Summary

## Overview

A CumulusCI task that updates Named Credential parameters in Salesforce orgs using the Tooling API. This task follows the same pattern as the `update_external_credential` task and is designed to work with the manageability rules of Named Credentials in Second-Generation Packages (2GP).

## Files

### 1. Main Task Implementation

**File:** `cumulusci/tasks/salesforce/update_named_credential.py`

**Key Components:**

-   `NamedCredentialCalloutOptions` - Pydantic model for callout configuration
-   `NamedCredentialHttpHeader` - Pydantic model for HTTP header configuration
-   `NamedCredentialParameter` - Pydantic model for parameter configuration
-   `TransformNamedCredentialParameter` - Supports reading values from environment variables
-   `UpdateNamedCredential` - Main task class that extends `BaseSalesforceApiTask`

**Supported Parameters:**

-   URL (endpoint URL)
-   Authentication (external credential reference)
-   Certificate (client certificate)
-   AllowedManagedPackageNamespaces
-   HttpHeader (with name, value, sequence number, secret flag)

**Supported Callout Options:**

-   allowMergeFieldsInBody
-   allowMergeFieldsInHeader
-   generateAuthorizationHeader

### 2. Comprehensive Test Suite

**File:** `cumulusci/tasks/salesforce/tests/test_update_named_credential.py`

**Test Coverage:**

-   Parameter model validation
-   Environment variable transformation
-   Successful updates
-   Error handling (not found, retrieve errors, update errors)
-   Namespace support
-   Multiple parameters
-   Adding new parameters
-   Sequence numbers
-   Callout options
-   Secured endpoint validation

**Test Results:** All tests passing ✓

### 3. Task Registration

**File:** `cumulusci/cumulusci.yml`

Task registration:

```yaml
update_named_credential:
    class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
    description: Update named credential parameters
    group: Metadata Transformations
```

### 4. Documentation

**Files:**

-   `docs/update_named_credential.md` - Comprehensive documentation
-   `QUICK_START_UPDATE_NAMED_CREDENTIAL.md` - Quick reference guide
-   `UPDATE_NAMED_CREDENTIAL_SUMMARY.md` - This summary document

## Usage Examples

### Basic Usage

```yaml
tasks:
    update_my_credential:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyNamedCredential
            parameters:
                - url: "https://api.example.com/v2/endpoint"
```

### With HTTP Headers

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
```

### With Environment Variables

```yaml
tasks:
    update_with_env:
        class_path: cumulusci.tasks.salesforce.update_named_credential.UpdateNamedCredential
        options:
            name: MyNamedCredential
            transform_parameters:
                - url: "API_ENDPOINT_URL"
                - http_header:
                      - name: "Authorization"
                        value: "API_TOKEN"
                        secret: true
```

### Command Line

```bash
cci task run update_named_credential \
    --org dev \
    -o name "MyNamedCredential" \
    -o parameters '[{"url": "https://api.example.com/v2/endpoint"}]'
```

## Key Features

1. **Flexible Parameter Updates**: Supports all Named Credential parameter types
2. **Environment Variable Support**: Use `transform_parameters` to read from env vars
3. **Secret Masking**: Mark parameters as secret to hide values in logs
4. **Namespace Support**: Works with namespaced and non-namespaced credentials
5. **Smart Parameter Matching**: Updates existing parameters or adds new ones
6. **Template-Based Creation**: Uses existing parameters as templates for consistency
7. **Comprehensive Error Handling**: Clear error messages for all failure scenarios
8. **2GP Compatibility**: Respects 2GP manageability rules
9. **Secured Endpoint Validation**: Only works with SecuredEndpoint named credentials
10. **Callout Options Support**: Update callout configuration options

## Implementation Pattern

The task follows the same architectural pattern as `UpdateExternalCredential`:

1. Query Tooling API to find the Named Credential by DeveloperName
2. Retrieve the full Named Credential metadata object
3. Validate that it's a SecuredEndpoint (required for updates)
4. Update parameters in-memory (add new or update existing)
5. Update callout options if provided
6. PATCH the updated metadata back to Salesforce
7. Log success or raise appropriate exceptions

## Parameter Validation

The task enforces that exactly one parameter type is provided per parameter object:

-   `url` - Endpoint URL
-   `authentication` - External credential reference
-   `certificate` - Client certificate
-   `allowed_managed_package_namespaces` - Allowed namespaces
-   `http_header` - List of HTTP headers

## HTTP Header Support

HTTP headers support:

-   `name` (required): Header name
-   `value` (required): Header value
-   `sequence_number` (optional): Order of execution
-   `secret` (optional): Hide value in logs

## Callout Options

The task supports updating callout options:

-   `allowMergeFieldsInBody`: Allow merge fields in request body
-   `allowMergeFieldsInHeader`: Allow merge fields in headers
-   `generateAuthorizationHeader`: Generate authorization header

## Testing

Run tests:

```bash
cd /Users/rupesh.j/Work/CumulusCI
python -m pytest cumulusci/tasks/salesforce/tests/test_update_named_credential.py -v
```

All tests pass successfully.

## Next Steps

The task is ready to use. To integrate into your project:

1. Ensure you're using the latest version of CumulusCI with this task
2. Add the task to your `cumulusci.yml` flows as needed
3. Configure parameters based on your Named Credential requirements
4. Use environment variables for sensitive values
5. Ensure your Named Credentials are of type "SecuredEndpoint"

## Related Tasks

-   `update_external_credential` - Updates External Credential parameters
-   Both tasks follow similar patterns and can be used together in flows

## References

-   [Salesforce Named Credentials](https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_callouts_named_credentials.htm)
-   [2GP Packageable Components](https://developer.salesforce.com/docs/atlas.en-us.pkg2_dev.meta/pkg2_dev/packaging_packageable_components.htm)
-   [CumulusCI Tasks](https://cumulusci.readthedocs.io/en/latest/tasks.html)
