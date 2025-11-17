"""SFDmu task for CumulusCI."""

import os
import shutil

import sarge

from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.core.sfdx import sfdx
from cumulusci.core.tasks import BaseSalesforceTask
from cumulusci.core.utils import determine_managed_mode
from cumulusci.tasks.command import Command


class SfdmuTask(BaseSalesforceTask, Command):
    """Execute SFDmu data migration with namespace injection support."""

    salesforce_task = (
        False  # Override to False since we manage our own org requirements
    )

    task_options = {
        "source": {
            "description": "Source org name (CCI org name like dev, beta, qa, etc.) or 'csvfile'",
            "required": True,
        },
        "target": {
            "description": "Target org name (CCI org name like dev, beta, qa, etc.) or 'csvfile'",
            "required": True,
        },
        "path": {
            "description": "Path to folder containing export.json and other CSV files",
            "required": True,
        },
        "additional_params": {
            "description": "Additional parameters to append to the sf sfdmu command (e.g., '--simulation --noprompt --nowarnings')",
            "required": False,
        },
    }

    def _init_options(self, kwargs):
        super()._init_options(kwargs)

        # Convert path to absolute path
        self.options["path"] = os.path.abspath(self.options["path"])

        # Validate that the path exists and contains export.json
        if not os.path.exists(self.options["path"]):
            raise TaskOptionsError(f"Path {self.options['path']} does not exist")

        export_json_path = os.path.join(self.options["path"], "export.json")
        if not os.path.exists(export_json_path):
            raise TaskOptionsError(f"export.json not found in {self.options['path']}")

    def _validate_org(self, org_name):
        """Validate that a CCI org exists and return the org config."""
        if org_name == "csvfile":
            return None

        try:
            if self.project_config.keychain is None:
                raise TaskOptionsError("No keychain available")
            org_config = self.project_config.keychain.get_org(org_name)
            return org_config
        except Exception as e:
            raise TaskOptionsError(f"Org '{org_name}' does not exist: {str(e)}")

    def _get_sf_org_name(self, org_config):
        """Get the SF org name from org config."""
        if hasattr(org_config, "sfdx_alias") and org_config.sfdx_alias:
            return org_config.sfdx_alias
        elif hasattr(org_config, "username") and org_config.username:
            return org_config.username
        else:
            raise TaskOptionsError("Could not determine SF org name for org config")

    def _create_execute_directory(self, base_path):
        """Create /execute directory and copy files from base_path."""
        execute_path = os.path.join(base_path, "execute")

        # Remove existing execute directory if it exists
        if os.path.exists(execute_path):
            shutil.rmtree(execute_path)

        # Create execute directory
        os.makedirs(execute_path, exist_ok=True)

        # Copy only files (not directories) from base_path to execute
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isfile(item_path) and item.endswith((".json", ".csv")):
                shutil.copy2(item_path, execute_path)

        return execute_path

    def _update_credentials(self):
        """Override to handle cases where org_config might be None."""
        # Only update credentials if we have an org_config
        if self.org_config is not None:
            super()._update_credentials()

    def _inject_namespace_tokens(
        self, execute_path, source_org_config, target_org_config
    ):
        """Inject namespace tokens into files in execute directory using the same mechanism as Deploy task."""
        # Determine which org config to use for namespace injection
        # When exporting (source=org, target=csvfile), use source org
        # When importing (source=csvfile, target=org), use target org
        # When transferring (source=org, target=org), use target org
        org_config_for_injection = (
            target_org_config if target_org_config is not None else source_org_config
        )

        if (
            org_config_for_injection is None
        ):  # both source and target are csvfile (unlikely but handle it)
            return

        # Get namespace information
        namespace = self.project_config.project__package__namespace
        managed = determine_managed_mode(
            self.options, self.project_config, org_config_for_injection
        )
        namespaced_org = bool(namespace) and namespace == getattr(
            org_config_for_injection, "namespace", None
        )

        # Create a temporary zipfile with all files from execute directory
        import tempfile
        import zipfile

        from cumulusci.core.dependencies.utils import TaskContext
        from cumulusci.core.source_transforms.transforms import (
            NamespaceInjectionOptions,
            NamespaceInjectionTransform,
        )

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
            temp_zip_path = temp_zip.name

        try:
            # Create zipfile with all files from execute directory
            with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(execute_path):
                    for file in files:
                        if file.endswith((".json", ".csv")):
                            file_path = os.path.join(root, file)
                            # Calculate relative path from execute_path
                            rel_path = os.path.relpath(file_path, execute_path)
                            zf.write(file_path, rel_path)

            # Apply namespace injection using the same mechanism as Deploy task
            with zipfile.ZipFile(temp_zip_path, "r") as zf:
                # Create namespace injection options
                options = NamespaceInjectionOptions(
                    namespace_tokenize=None,
                    namespace_inject=namespace,
                    namespace_strip=None,
                    unmanaged=not managed,
                    namespaced_org=namespaced_org,
                )

                # Create transform
                transform = NamespaceInjectionTransform(options)

                # Create task context
                context = TaskContext(
                    org_config_for_injection, self.project_config, self.logger
                )

                # Apply namespace injection
                new_zf = transform.process(zf, context)

                # Extract processed files back to execute directory
                # First, remove all existing files
                for root, dirs, files in os.walk(execute_path):
                    for file in files:
                        if file.endswith((".json", ".csv")):
                            os.remove(os.path.join(root, file))

                # Extract processed files
                for file_info in new_zf.infolist():
                    if file_info.filename.endswith((".json", ".csv")):
                        # Extract to execute directory
                        target_path = os.path.join(execute_path, file_info.filename)
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with new_zf.open(file_info) as source:
                            with open(target_path, "wb") as target:
                                target.write(source.read())

                        self.logger.info(
                            f"Applied namespace injection to {file_info.filename}"
                        )

        finally:
            # Clean up temporary zipfile
            if os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)

    def _run_task(self):
        """Execute the SFDmu task."""
        # Validate source and target orgs
        source_org_config = self._validate_org(self.options["source"])
        target_org_config = self._validate_org(self.options["target"])

        # Get SF org names
        if source_org_config:
            source_sf_org = self._get_sf_org_name(source_org_config)
        else:
            source_sf_org = "csvfile"

        if target_org_config:
            target_sf_org = self._get_sf_org_name(target_org_config)
        else:
            target_sf_org = "csvfile"

        # Create execute directory and copy files
        execute_path = self._create_execute_directory(self.options["path"])
        self.logger.info(f"Created execute directory at {execute_path}")

        # Apply namespace injection
        self._inject_namespace_tokens(
            execute_path, source_org_config, target_org_config
        )

        # Build and execute SFDmu command
        # Use shell_quote to properly handle paths with spaces on Windows
        command_parts = [
            "-s",
            source_sf_org,
            "-u",
            target_sf_org,
            "-p",
            execute_path,
        ]

        # Append additional parameters if provided
        if self.options.get("additional_params"):
            # Split the additional_params string into individual arguments
            # This handles cases like "-no-warnings -m -t error" -> ["-no-warnings", "-m", "-t", "error"]
            additional_args = self.options["additional_params"].split()
            # Quote each argument to handle spaces properly
            command_parts.extend(additional_args)

        # Join command parts into a single string for sarge (which uses shell=True)
        command = "sf sfdmu run " + " ".join(command_parts)
        self.logger.info(f"Executing: {command}")

        p: sarge.Command = sfdx(
            "sfdmu run",
            log_note="Running SFDmu",
            args=command_parts,
            check_return=True,
            username=None,
        )

        for line in p.stdout_text:
            self.logger.info(line)

        for line in p.stderr_text:
            self.logger.error(line)

        self.logger.info("SFDmu task completed successfully")
