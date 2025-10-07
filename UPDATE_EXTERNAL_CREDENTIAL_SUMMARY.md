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
-   AuthProvider (subscriber editable in 2GP)
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

-   23 test cases covering:
    -   Parameter model validation
    -   Environment variable transformation
    -   Successful updates
    -   Error handling (not found, retrieve errors, update errors)
    -   Namespace support
    -   Multiple parameters
    -   Adding new parameters
    -   Sequence numbers

**Test Results:** All 23 tests passing ✓

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

All 23 tests pass successfully.

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
