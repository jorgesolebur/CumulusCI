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
