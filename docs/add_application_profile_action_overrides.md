# add_applications_profile_action_overrides Task

## Overview

The `add_applications_profile_action_overrides` task allows you to add or update `profileActionOverrides` in Salesforce Custom Application metadata files. This is useful for customizing how different profiles interact with standard Salesforce actions (View, Edit, New, etc.) by redirecting them to custom Lightning pages, Visualforce pages, or Lightning components.

## Task Class

```python
from cumulusci.tasks.metadata_etl.applications import AddProfileActionOverrides
```

## Task Options

### Required Options

- **applications**: List of CustomApplication configurations, each containing:
  - **name**: API name of the CustomApplication to modify
  - **overrides**: List of profileActionOverride configurations for this application

### Override Configuration Structure

Each override in the application's `overrides` list requires the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action_name` | string | Yes | The action to override (e.g., "View", "Edit", "New") |
| `content` | string | Yes | API name of the Lightning page, Visualforce page, or component |
| `form_factor` | string | Yes | Form factor for the override (e.g., "Large", "Small") |
| `page_or_sobject_type` | string | Yes | The SObject API name this override applies to |
| `record_type` | string | No | Record type API name (format: "SObject.RecordType") |
| `type` | string | Yes | Type of override ("Flexipage", "Visualforce", "LightningComponent") |
| `profile` | string | Yes | Profile name or API name this override applies to |

## Behavior

### Adding New Overrides
When a profileActionOverride doesn't exist, it will be added to the application metadata.

### Updating Existing Overrides
If a profileActionOverride already exists with the same `action_name`, `page_or_sobject_type`, `record_type`, and `profile`, it will be **updated** with the new values and a warning will be logged.

### Matching Logic
The task identifies duplicate overrides by matching on:
1. `action_name`
2. `page_or_sobject_type`
3. `record_type` (can be null)
4. `profile`

## Example Usage

### Basic Example - Single Override

```yaml
  add_applications_profile_action_overrides:
    options:
      applications:
        - name: "AdministrationConsole"
          overrides:
            - action_name: View
              content: CustomAccountRecordPage
              form_factor: Large
              page_or_sobject_type: Account
              record_type: PersonAccount.User
              type: Flexipage
              profile: Admin
```

### Multiple Overrides Example

```yaml
  add_applications_profile_action_overrides:
    options:
      applications:
        - name: "AdministrationConsole"
          overrides:
            - action_name: View
              content: AccountUserRecordPage
              form_factor: Large
              page_or_sobject_type: Account
              record_type: PersonAccount.User
              type: Flexipage
              profile: CustomerBusinessPersona
            - action_name: View
              content: IdentifierNonTerminologyRecordPage
              form_factor: Large
              page_or_sobject_type: Identifier
              record_type: Identifier.NonTerminology
              type: Flexipage
              profile: CustomerBusinessPersona
            - action_name: View
              content: AccountUserRecordPage
              form_factor: Large
              page_or_sobject_type: Account
              record_type: PersonAccount.User
              type: Flexipage
              profile: Admin
```

### Override Without Record Type

```yaml
  add_applications_profile_action_overrides:
    options:
      applications:
        - name: "SalesConsole"
          overrides:
            - action_name: New
              content: CustomContactPage
              form_factor: Large
              page_or_sobject_type: Contact
              record_type: null  # or omit this field
              type: Visualforce
              profile: StandardUser
```

### With Namespace Injection

```yaml
  add_applications_profile_action_overrides:
    options:
      managed: True
      applications:
        - name: "%%%NAMESPACE%%%AdministrationConsole"
          overrides:
            - action_name: View
              content: %%%NAMESPACED_ORG%%%CustomRecordPage
              form_factor: Large
              page_or_sobject_type: %%%NAMESPACE%%%CustomObject__c
              record_type: %%%NAMESPACE%%%CustomObject__c.%%%NAMESPACE%%%CustomRecordType
              type: Flexipage
              profile: Admin
```

## Integration with CumulusCI Flows

### Adding to a Flow

```yaml
flows:
  config_managed:
    steps:
      # ... other steps ...
      5.1:
        task: add_applications_profile_action_overrides
        options:
          applications:
            - name: "AdministrationConsole"
              overrides:
                - action_name: View
                  content: %%%NAMESPACE%%%CustomPage
                  form_factor: Large
                  page_or_sobject_type: Account
                  type: Flexipage
                  profile: Admin
```

## Running the Task

### From Command Line

```bash
# Basic usage
cci task run add_applications_profile_action_overrides \
  --applications '[{"name":"AdministrationConsole","overrides":[{"action_name":"View","content":"CustomPage","form_factor":"Large","page_or_sobject_type":"Account","type":"Flexipage","profile":"Admin"}]}]' \
  --org dev

# With namespace injection
cci task run add_applications_profile_action_overrides \
  --managed True \
  --applications '[{"name":"%%%NAMESPACE%%%AdministrationConsole","overrides":[{"action_name":"View","content":"%%%NAMESPACE%%%CustomPage","form_factor":"Large","page_or_sobject_type":"Account","type":"Flexipage","profile":"Admin"}]}]' \
  --org dev
```

### From Python

```python
from cumulusci.core.runtime import BaseCumulusCI
from cumulusci.tasks.metadata_etl.applications import AddProfileActionOverrides

# Configure and run task
task_config = {
    "options": {
        "applications": [
            {
                "name": "AdministrationConsole",
                "overrides": [
                    {
                        "action_name": "View",
                        "content": "CustomPage",
                        "form_factor": "Large",
                        "page_or_sobject_type": "Account",
                        "type": "Flexipage",
                        "profile": "Admin"
                    }
                ]
            }
        ]
    }
}

task = AddProfileActionOverrides(
    runtime.project_config,
    TaskConfig(task_config),
    runtime.keychain.get_default_org()
)
task()
```

## Common Use Cases

### 1. Custom Record Pages for Different Profiles

Override the View action to show different record pages based on profile:

```yaml
applications:
  - name: "AdministrationConsole"
    overrides:
      - action_name: View
        content: AdminAccountPage
        form_factor: Large
        page_or_sobject_type: Account
        type: Flexipage
        profile: Admin
      - action_name: View
        content: StandardUserAccountPage
        form_factor: Large
        page_or_sobject_type: Account
        type: Flexipage
        profile: StandardUser
```

### 2. Record Type Specific Overrides

Show different pages for different record types:

```yaml
applications:
  - name: "AdministrationConsole"
    overrides:
      - action_name: View
        content: PersonAccountPage
        form_factor: Large
        page_or_sobject_type: Account
        record_type: PersonAccount.User
        type: Flexipage
        profile: Admin
      - action_name: View
        content: BusinessAccountPage
        form_factor: Large
        page_or_sobject_type: Account
        record_type: Account.Business
        type: Flexipage
        profile: Admin
```

### 3. Mobile Overrides

Provide different experiences for mobile:

```yaml
applications:
  - name: "MobileConsole"
    overrides:
      - action_name: View
        content: DesktopAccountPage
        form_factor: Large
        page_or_sobject_type: Account
        type: Flexipage
        profile: Admin
      - action_name: View
        content: MobileAccountPage
        form_factor: Small
        page_or_sobject_type: Account
        type: Flexipage
        profile: Admin
```

### 4. Multiple Applications in One Task

Configure overrides for multiple applications at once:

```yaml
applications:
  - name: "AdminConsole"
    overrides:
      - action_name: View
        content: AdminAccountView
        form_factor: Large
        page_or_sobject_type: Account
        type: Flexipage
        profile: Admin
      - action_name: Edit
        content: AdminAccountEdit
        form_factor: Large
        page_or_sobject_type: Account
        type: Flexipage
        profile: Admin
  - name: "SalesConsole"
    overrides:
      - action_name: View
        content: SalesContactView
        form_factor: Large
        page_or_sobject_type: Contact
        type: Flexipage
        profile: SalesUser
  - name: "ServiceConsole"
    overrides:
      - action_name: View
        content: ServiceCaseView
        form_factor: Large
        page_or_sobject_type: Case
        type: Flexipage
        profile: ServiceUser
```

## Troubleshooting

### Override Not Applied

**Issue**: The override exists but isn't being applied in Salesforce.

**Solutions**:
- Verify the profile name matches exactly (case-sensitive)
- Ensure the Lightning page/Visualforce page exists and is activated
- Check that the Lightning page is assigned to the correct app and record type
- Verify form factor matches the device being tested

### Duplicate Override Warning

**Issue**: Getting warnings about existing overrides being updated.

**Solutions**:
- This is expected behavior when an override already exists
- Review the existing override before running to ensure you want to update it
- Different profiles, record types, or form factors are treated as separate overrides

### Namespace Injection Not Working

**Issue**: Namespace tokens aren't being replaced.

**Solutions**:
- Ensure `managed: True` is set in task options
- Use correct namespace tokens (%%%NAMESPACE%%% for content tokens)
- Verify your project has a namespace configured in `cumulusci.yml`

## Best Practices

1. **Test in Scratch Orgs**: Always test overrides in a scratch org before deploying to production
2. **Document Changes**: Keep a record of which overrides are configured and why
3. **Use Namespace Tokens**: Always use namespace injection tokens for managed packages
4. **Profile Names**: Use exact profile names - they're case-sensitive
5. **Version Control**: Keep your override configurations in version control
6. **Incremental Updates**: Add overrides incrementally and test each addition

## Related Metadata API Documentation

- [ProfileActionOverride](https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_profileactionoverride.htm)
- [CustomApplication](https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_customapplication.htm)

