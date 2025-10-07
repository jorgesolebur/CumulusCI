# SFDmu Task

This task provides integration between CumulusCI and SFDmu (Salesforce Data Migration Utility) with namespace injection support.

## Usage

```bash
cci task run sfdmu --source dev --target qa --path /path/to/sfdmu/folder
```

## Options

- `source`: Source org name (CCI org name like dev, beta, qa, etc.) or 'csvfile'
- `target`: Target org name (CCI org name like dev, beta, qa, etc.) or 'csvfile'  
- `path`: Path to folder containing export.json and other CSV files

## Features

- **Org Validation**: Validates that source and target CCI orgs exist
- **Namespace Injection**: Automatically injects namespace tokens into JSON and CSV files
- **File Processing**: Copies files to an execute directory and processes namespace tokens
- **Real-time Output**: Streams SFDmu command output in real-time
- **Error Handling**: Returns appropriate errors if SFDmu command fails

## Requirements

- SFDmu must be installed and available in PATH
- Source folder must contain `export.json`
- Valid CCI org configurations for source and target (unless using 'csvfile')

## Namespace Token Support

The task supports the following namespace tokens:
- `%%%NAMESPACE%%%` - Replaced with namespace prefix
- `%%%NAMESPACED_ORG%%%` - Replaced with namespaced org prefix
- `___NAMESPACE___` - Replaced in filenames
- `___NAMESPACED_ORG___` - Replaced in filenames
- `%%%ALWAYS_NAMESPACE%%%` - **Always** replaced with namespace prefix (if namespace exists), regardless of managed/unmanaged context
- `___ALWAYS_NAMESPACE___` - **Always** replaced in filenames with namespace prefix (if namespace exists), regardless of managed/unmanaged context

### Special Tokens: %%%ALWAYS_NAMESPACE%%% and ___ALWAYS_NAMESPACE___

The `%%%ALWAYS_NAMESPACE%%%` and `___ALWAYS_NAMESPACE___` tokens are processed after the standard namespace injection and will always be replaced with the namespace prefix (e.g., `myns__`) if a namespace is available, regardless of whether the deployment is in managed or unmanaged mode. This is useful when you need to ensure namespace prefixes are always applied to certain fields or filenames.

**Content Token Example:**
```json
{
  "object": "%%%ALWAYS_NAMESPACE%%%CustomObject__c",
  "field": "%%%NAMESPACE%%%CustomField__c"
}
```

**Filename Token Example:**
```
___ALWAYS_NAMESPACE___data.json
mydata___ALWAYS_NAMESPACE___.csv
```

In these examples:
- `%%%ALWAYS_NAMESPACE%%%CustomObject__c` will always become `myns__CustomObject__c` (if namespace is `myns`)
- `%%%NAMESPACE%%%CustomField__c` will become `myns__CustomField__c` in managed mode or `CustomField__c` in unmanaged mode
- `___ALWAYS_NAMESPACE___data.json` will always become `myns__data.json` (if namespace is `myns`)
- `mydata___ALWAYS_NAMESPACE___.csv` will always become `mydatamyns__.csv` (if namespace is `myns`)

## Example

```bash
# Migrate data from dev org to qa org
cci task run sfdmu --source dev --target qa --path datasets/migration

# Migrate data from CSV files to dev org
cci task run sfdmu --source csvfile --target dev --path datasets/csv_data
```
