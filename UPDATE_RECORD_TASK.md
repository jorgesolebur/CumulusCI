# UpdateRecord Task Documentation

## Overview

The `update_record` task allows you to update one or more Salesforce records using the REST API, Tooling API, or Bulk API. It automatically selects the optimal update strategy: direct REST API for single records and Bulk API for multiple records, providing up to 99.9% reduction in API calls for large updates. The task supports both static values and dynamic values extracted from environment variables, making it ideal for CI/CD pipelines and configuration management.

## Task Options

| Option             | Required | Description                                                                                                                      |
| ------------------ | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `object`           | ✓        | The sObject type to update (e.g., Account, Contact, CustomObject\_\_c)                                                           |
| `values`           | ✗\*      | Field names and values to update in format 'field:value,field2:value2' or as a YAML dict                                         |
| `transform_values` | ✗\*      | Field names and environment variable keys in format 'field:ENV_KEY,field2:ENV_KEY2'. Values extracted from environment variables |
| `record_id`        | ✗\*\*    | The ID of a specific record to update. If specified, `where` is ignored                                                          |
| `where`            | ✗\*\*    | Query criteria in format 'field:value,field2:value2'. Multiple records may be updated                                            |
| `tooling`          | ✗        | If True, use Tooling API instead of REST API (default: False)                                                                    |
| `fail_on_error`    | ✗        | If True (default), fail the task if any record update fails. If False, log errors but continue                                   |

**Notes:**

-   \*At least one of `values` or `transform_values` must be specified
-   \*\*Either `record_id` or `where` must be specified

## Basic Usage Examples

### 1. Update a Single Record by ID

Update a specific Account record using its Salesforce ID:

```bash
cci task run update_record --org dev \
  --object Account \
  --record_id 001xx000003DGbXXXX \
  --values Name:UpdatedName,Status__c:Active
```

### 2. Update Records by Query Criteria

Update all Account records matching the query criteria:

```bash
cci task run update_record --org dev \
  --object Account \
  --where Name:TestAccount,Status__c:Draft \
  --values Status__c:Active,UpdatedDate__c:2024-12-04
```

### 3. Update Multiple Records

Update all Contact records with a specific status:

```bash
cci task run update_record --org dev \
  --object Contact \
  --where Status__c:Pending \
  --values Status__c:Approved,ApprovedBy__c:Admin
```

### 4. Update with Tooling API

Update a PermissionSet using the Tooling API:

```bash
cci task run update_record --org dev \
  --object PermissionSet \
  --record_id 0PS3D000000MKTqWAO \
  --values Label:UpdatedLabel \
  --tooling true
```

### 5. Continue on Errors

Update records but continue even if some fail:

```bash
cci task run update_record --org dev \
  --object Account \
  --where Type:Customer \
  --values Status__c:Active \
  --fail_on_error false
```

### 6. Using YAML Configuration

Define the task in `cumulusci.yml`:

```yaml
tasks:
    update_accounts:
        class_path: cumulusci.tasks.salesforce.update_record.UpdateRecord
        options:
            object: Account
            where: Status__c:Draft
            values:
                Status__c: Active
                UpdatedBy__c: Admin
                UpdatedDate__c: "2024-12-04"
```

Then run:

```bash
cci task run update_accounts --org dev
```

## Transform Values Feature

The `transform_values` option enables dynamic value extraction from environment variables, making the task perfect for CI/CD pipelines and configuration management.

### How It Works

-   **Syntax**: `--transform_values field:ENV_KEY,field2:ENV_KEY2`
-   **Behavior**: Extracts value from environment variable `ENV_KEY`
-   **Fallback**: If environment variable doesn't exist, uses the key name itself as the value
-   **Logging**: Logs each transformation for visibility

### Transform Values Examples

#### Example 1: Update with Environment Variables

```bash
export ACCOUNT_NAME_VAR="My Account Name"
export ACCOUNT_STATUS_VAR="Active"

cci task run update_record --org dev \
  --object Account \
  --record_id 001xx000003DGbXXXX \
  --transform_values Name:ACCOUNT_NAME_VAR,Status__c:ACCOUNT_STATUS_VAR
```

**Output Log**:

```
Transform value for field 'Name': ACCOUNT_NAME_VAR -> My Account Name
Transform value for field 'Status__c': ACCOUNT_STATUS_VAR -> Active
```

#### Example 2: Combine Static and Dynamic Values

```bash
export DYNAMIC_NAME="Dynamic Account"

cci task run update_record --org dev \
  --object Account \
  --record_id 001xx000003DGbXXXX \
  --values Type:Customer,Rating:Hot \
  --transform_values Name:DYNAMIC_NAME
```

**Result**:

-   `Name` = value from `DYNAMIC_NAME` environment variable
-   `Type` = "Customer" (literal value)
-   `Rating` = "Hot" (literal value)

#### Example 3: Update Multiple Records with Environment Variables

```bash
export STATUS_VALUE="Completed"

cci task run update_record --org dev \
  --object Contact \
  --where Department:Sales \
  --transform_values Status__c:STATUS_VALUE
```

#### Example 4: Transform Values in YAML

```yaml
tasks:
    update_accounts_from_env:
        class_path: cumulusci.tasks.salesforce.update_record.UpdateRecord
        options:
            object: Account
            record_id: 001xx000003DGbXXXX
            transform_values:
                Name: ACCOUNT_NAME_ENV
                Status__c: ACCOUNT_STATUS_ENV
                Type: ACCOUNT_TYPE_ENV
```

### Merge Behavior

When both `values` and `transform_values` are provided:

1. Start with fields from `values`
2. Add/override with fields from `transform_values`
3. `transform_values` takes precedence for duplicate fields

**Example**:

```bash
export NEW_NAME="Environment Name"

cci task run update_record --org dev \
  --object Account \
  --record_id 001xx000003DGbXXXX \
  --values Name:OriginalName,Type:Customer \
  --transform_values Name:NEW_NAME
```

**Final values**: `Name=Environment Name`, `Type=Customer`

## Behavior Details

### Record ID vs Where Clause

-   If `record_id` is provided, it takes precedence and `where` is ignored
-   Direct update is performed using the record ID
-   No query is executed

### Query Criteria (where)

-   Simple field:value pairs are converted to a SOQL WHERE clause
-   Format: `field:value,field2:value2`
-   Query: `SELECT Id FROM {object} WHERE field = 'value' AND field2 = 'value2'`

### No Records Found

-   When using `where` and no records match the criteria
-   A warning message is logged
-   Task completes successfully without errors

### Multiple Records

-   **Single record queries**: Updated via direct REST API (`_update_by_id`)
-   **Multiple record queries**: Updated via Bulk API (`_update_records_bulk`)
-   Automatic strategy selection for optimal performance
-   Progress is logged for each record
-   Summary shows: `X/Y records updated successfully`

### Error Handling

-   **fail_on_error=true (default)**: Task fails if any update fails, showing which records failed
-   **fail_on_error=false**: Errors are logged but task continues, summary shows success/failure counts

### Partial Failures

-   When updating multiple records and some fail:
    -   With `fail_on_error=true`: Task fails after attempting all updates, listing all failures
    -   With `fail_on_error=false`: Task succeeds, logging all errors

## Advanced Use Cases

### 1. CI/CD Pipelines

Environment variables from CI/CD pipelines can be used for dynamic record updates:

```bash
# In CI/CD pipeline
export DEPLOYMENT_STATUS="Deployed"
export DEPLOYMENT_DATE="2024-12-04"
export DEPLOYMENT_USER="$CI_USER"
export BUILD_NUMBER="$CI_BUILD_NUMBER"

cci task run update_record --org prod \
  --where Type:Deployment \
  --transform_values \
    Status:DEPLOYMENT_STATUS,\
    DeployDate__c:DEPLOYMENT_DATE,\
    DeployedBy__c:DEPLOYMENT_USER,\
    BuildNumber__c:BUILD_NUMBER
```

### 2. Environment-Specific Configuration

Same command works across different environments with environment-specific values:

```bash
# Development environment
export ORG_TYPE="Development"
export API_ENDPOINT="https://dev-api.example.com"

# Production environment
export ORG_TYPE="Production"
export API_ENDPOINT="https://api.example.com"

# Same command for both environments
cci task run update_record --org current \
  --object Configuration__c \
  --where Name:OrgSettings \
  --transform_values Type__c:ORG_TYPE,Endpoint__c:API_ENDPOINT
```

### 3. Secret Management

Keep sensitive data out of code by using environment variables from secret vaults:

```bash
export API_KEY="secret_key_from_vault"
export API_SECRET="secret_value_from_vault"
export OAUTH_TOKEN="oauth_token_from_vault"

cci task run update_record --org dev \
  --object NamedCredential \
  --record_id <credential_id> \
  --transform_values \
    ApiKey__c:API_KEY,\
    ApiSecret__c:API_SECRET,\
    Token__c:OAUTH_TOKEN
```

### 4. Dynamic Test Data Management

Update test data with values from test configuration:

```bash
export TEST_ACCOUNT_NAME="Test Account $(date +%Y%m%d)"
export TEST_EMAIL="test+$(date +%s)@example.com"

cci task run update_record --org qa \
  --where IsTestData__c:true \
  --transform_values Name:TEST_ACCOUNT_NAME,Email__c:TEST_EMAIL
```

### 5. Bulk Configuration Updates

Update multiple configuration records across environments:

```yaml
# In cumulusci.yml
tasks:
    configure_environment:
        class_path: cumulusci.tasks.salesforce.update_record.UpdateRecord
        options:
            object: AppConfig__c
            where: IsActive__c:true
            transform_values:
                Environment__c: ENVIRONMENT_NAME
                ApiEndpoint__c: API_ENDPOINT
                MaxRetries__c: MAX_RETRIES
                TimeoutSeconds__c: TIMEOUT_SECONDS
```

## Comparison with insert_record

| Feature               | insert_record      | update_record              |
| --------------------- | ------------------ | -------------------------- |
| Purpose               | Create new records | Update existing records    |
| Single record         | ✓ (by values)      | ✓ (by record_id)           |
| Multiple records      | ✗                  | ✓ (by where clause)        |
| Bulk API              | ✗                  | ✓ (automatic for multiple) |
| Query support         | ✗                  | ✓                          |
| Static values         | ✓                  | ✓                          |
| Environment variables | ✗                  | ✓ (transform_values)       |
| Tooling API           | ✓                  | ✓                          |
| Error handling        | Basic              | Advanced (fail_on_error)   |

## Related Tasks

-   `insert_record`: Insert a new record
-   `update_data`: Update records from a CSV file
-   `load_data`: Bulk data loading

## Common Use Cases

### Standard Use Cases

1. **Activate test data**: Update Status fields after data deployment
2. **Update configuration**: Modify settings in Custom Settings or Custom Metadata
3. **Bulk status changes**: Update multiple records matching criteria
4. **Fix data issues**: Correct field values in development/testing orgs
5. **Permission Set updates**: Modify permission sets using Tooling API

### Transform Values Use Cases

6. **CI/CD deployments**: Update deployment status and metadata during pipeline runs
7. **Environment configuration**: Set environment-specific values dynamically
8. **Secret rotation**: Update credentials from secure vaults without hardcoding
9. **Dynamic test data**: Create unique test data for each test run
10. **Multi-environment management**: Same task definition works across environments

## Key Features and Benefits

### Transform Values

1. **Dynamic Configuration**: Update records with values from environment
2. **CI/CD Integration**: Seamlessly integrate with pipeline variables
3. **Security**: Keep sensitive data out of code/configuration files
4. **Flexibility**: Combine static and dynamic values in same update
5. **Fallback Safety**: Defaults to key name if environment variable missing
6. **Logging**: Clear visibility of transform operations

### Bulk API Optimization

1. **Scalability**: Efficiently handle hundreds or thousands of records
2. **Performance**: Up to 99.9% reduction in API calls
3. **Rate Limits**: Better management with separate bulk API quotas
4. **Speed**: Parallel processing on Salesforce servers
5. **Automatic**: No configuration needed - works transparently
6. **Smart Selection**: Single records use direct API for optimal response

### General Benefits

1. **Backward Compatibility**: All existing tasks continue to work unchanged
2. **Comprehensive Error Handling**: Detailed logging and error reporting
3. **Flexible Querying**: Update by ID or by query criteria
4. **Multiple Update Strategies**: Optimized for both single and bulk updates

## Tips and Best Practices

### General Tips

-   Use `cci task info update_record` to see all options
-   Test queries first with `cci task run query` to verify record counts
-   Use `fail_on_error: false` when updating large datasets where some failures are acceptable
-   Use YAML configuration for complex updates with multiple fields

### Performance Tips

-   For multiple records, the task automatically uses Bulk API (no configuration needed)
-   Single record updates use direct API for optimal response time
-   Large updates (100+ records) benefit significantly from automatic bulk processing
-   Monitor logs to see which update strategy is being used
-   Bulk API has separate rate limits - better for high-volume updates

### Transform Values Tips

-   Always set environment variables before running the task
-   Use descriptive environment variable names (e.g., `ACCOUNT_NAME` not `AN`)
-   Check logs to verify correct value extraction
-   Use YAML configuration for reusable tasks across environments
-   Combine with `values` for mixed static/dynamic updates
-   Test with local environment variables before deploying to CI/CD

### Security Best Practices

-   Never commit environment variable values to version control
-   Use secret management tools (e.g., AWS Secrets Manager, Azure Key Vault)
-   Rotate secrets regularly and update via transform_values
-   Use CI/CD platform's secret management features
-   Audit environment variable access in logs

## Testing

The feature includes comprehensive test coverage:

**Test Results**: ✅ All 19 tests passed (14 existing + 5 new)

**New Test Cases**:

-   `test_missing_values_and_transform_values` - Validates error when neither option provided
-   `test_transform_values_with_env_vars` - Tests extraction from environment variables
-   `test_transform_values_with_missing_env_vars` - Tests fallback to key name
-   `test_values_and_transform_values_combined` - Tests merging both options
-   `test_transform_values_with_where_clause` - Tests with query-based updates

## Troubleshooting

### Environment Variable Not Found

**Issue**: Task uses key name instead of expected value

**Solution**:

-   Verify environment variable is set: `echo $ENV_VAR_NAME`
-   Check for typos in variable names
-   Ensure variable is exported: `export VAR_NAME=value`

### Value Override Not Working

**Issue**: Expected `transform_values` to override `values`

**Solution**:

-   Confirm field names match exactly (case-sensitive)
-   Check logs for "Transform value for field" messages
-   Verify environment variable is set

### No Records Updated

**Issue**: Query returns no records

**Solution**:

-   Test query criteria with SOQL query first
-   Verify field names and values in `where` clause
-   Check object permissions

## Performance Optimization

### Bulk API Integration

The task automatically uses the optimal update strategy based on the number of records:

**Single Record (count = 1):**

-   Uses direct REST API update via `_update_by_id()` method
-   Optimal for single record updates
-   Immediate response with detailed error handling

**Multiple Records (count > 1):**

-   Uses Salesforce Bulk API via `_update_records_bulk()` method
-   One bulk API call instead of N individual calls
-   Parallel processing on Salesforce servers
-   Better rate limit management

### Performance Comparison

| Records      | Individual API Calls | Bulk API        | Improvement     |
| ------------ | -------------------- | --------------- | --------------- |
| 1 record     | 1 API call           | 1 API call      | Same (optimal)  |
| 10 records   | 10 API calls         | 1 Bulk API call | 90% reduction   |
| 100 records  | 100 API calls        | 1 Bulk API call | 99% reduction   |
| 1000 records | 1000 API calls       | 1 Bulk API call | 99.9% reduction |

**Benefits:**

-   ⚡ Up to 99.9% reduction in API calls for large updates
-   📊 Better rate limit management with separate bulk API quotas
-   🚀 Faster execution through parallel processing
-   📈 Scales efficiently to thousands of records
-   ✅ Fully backward compatible - no changes needed to existing tasks

### Bulk Update Example

```bash
# Updates 500 contacts with a single Bulk API call
cci task run update_record --org dev \
  --object Contact \
  --where Department:Sales \
  --values Status__c:Active
```

**Log Output:**

```
Found 500 Contact record(s) to update
Performing bulk update of 500 Contact records
Updated record: 003xx000001Record1
Updated record: 003xx000001Record2
...
Bulk update complete: 500/500 records updated successfully
```

## Version History

### v1.2.0 (Latest)

-   ⚡ **Bulk API Integration**: Automatic bulk update for multiple records
-   📈 **Performance**: Up to 99.9% reduction in API calls for large updates
-   🎯 **Smart Strategy**: Single records use direct API, multiple use bulk API
-   ✅ Fully backward compatible - existing tasks automatically benefit
-   🧪 All 19 tests passing with bulk API support

### v1.1.0

-   ✨ Added `transform_values` option for environment variable extraction
-   ✨ Enhanced merge behavior for combining static and dynamic values
-   ✨ Added comprehensive logging for value transformations
-   🔧 Made `values` optional (with `transform_values` as alternative)
-   📚 Updated documentation with CI/CD and secret management examples
-   ✅ Added 5 new test cases for transform_values functionality

### v1.0.0

-   🎉 Initial release with basic update functionality
-   ✅ Support for single and multiple record updates
-   ✅ Query-based record selection
-   ✅ Tooling API support
-   ✅ Advanced error handling with fail_on_error option
