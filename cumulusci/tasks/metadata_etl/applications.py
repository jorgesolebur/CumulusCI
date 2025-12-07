from typing import List, Optional, Set
from urllib.parse import quote

from pydantic.v1 import BaseModel

from cumulusci.tasks.metadata_etl import MetadataSingleEntityTransformTask
from cumulusci.utils import inject_namespace
from cumulusci.utils.xml.metadata_tree import MetadataElement


def _inject_namespace(text: str, options: dict) -> str:
    return inject_namespace(
        "",
        text,
        namespace=options["namespace_inject"]
        if not options.get("namespaced_org")
        else "",
        managed=options.get("managed") or False,
        namespaced_org=options.get("namespaced_org"),
    )[1]


class ProfileActionOverrideOptions(BaseModel):
    """Options for a single profileActionOverride"""

    action_name: str
    content: str
    form_factor: str
    page_or_sobject_type: str
    record_type: Optional[str]
    type: str
    profile: str
    options: dict = {}

    def namespace_inject(self, field_name: str) -> None:
        setattr(
            self, field_name, _inject_namespace(getattr(self, field_name), self.options)
        )


class AddProfileActionOverridesOptions(BaseModel):
    """Options container for profile action overrides"""

    name: str
    overrides: List[ProfileActionOverrideOptions]


class AddProfileActionOverrides(MetadataSingleEntityTransformTask):
    """
    Inserts or updates profileActionOverrides in CustomApplication metadata.
    If a profileActionOverride with the same actionName, pageOrSobjectType,
    recordType, and profile already exists, it will be updated with a warning.
    Otherwise, a new override will be added.
    Task option details:
    - applications: List of CustomApplications to modify
        - name: API name of the CustomApplication to modify
        - overrides: List of profile action overrides to add/update
            - action_name: Action name (e.g., "View", "Edit", "New")
            - content: Content reference (page/component API name)
            - form_factor: Form factor (e.g., "Large", "Small")
            - page_or_sobject_type: Page or SObject type
            - record_type: Record type API name (optional)
            - type: Override type (e.g., "Flexipage", "Visualforce", "LightningComponent")
            - profile: Profile name or API name
    Example Usage
    -----------------------
    .. code-block::  yaml
        task: add_profile_action_overrides
        options:
            applications:
                - name: "%%%NAMESPACE%%%CustomApplicationConsole"
                  overrides:
                    - action_name: View
                      content: "%%%NAMESPACED_ORG%%%AccountUserRecordPage"
                      form_factor: Large
                      page_or_sobject_type: Account
                      record_type: PersonAccount.User
                      type: Flexipage
                      profile: Admin
    """

    entity = "CustomApplication"
    task_options = {
        "applications": {
            "description": "List of CustomApplications to modify. See task info for structure.",
            "required": True,
        },
        **MetadataSingleEntityTransformTask.task_options,
    }

    def _init_options(self, kwargs):
        super()._init_options(kwargs)

        # Validate options using Pydantic
        self._validated_options: List[AddProfileActionOverridesOptions] = []
        for application in self.options.get("applications"):
            validated_options = AddProfileActionOverridesOptions(
                name=quote(_inject_namespace(application.get("name"), self.options)),
                overrides=application.get("overrides"),
            )

            self._validated_options.append(validated_options)

        self.api_names: Set[str] = set(
            application.name for application in self._validated_options
        )

    def _transform_entity(
        self, metadata: MetadataElement, api_name: str
    ) -> Optional[MetadataElement]:

        if not self._validated_options:
            self.logger.warning("No applications to add profile action overrides for")
            return None

        for application in self._validated_options:
            if application.name != api_name:
                continue

            for override_config in application.overrides:
                self._add_or_update_override(
                    metadata, application.name, override_config
                )

        return metadata

    def _add_or_update_override(self, metadata, api_name, override_config):
        """Add or update a single profileActionOverride"""
        override_config.options = self.options

        # Inject namespace where needed
        override_config.namespace_inject("content")
        override_config.namespace_inject("page_or_sobject_type")
        override_config.namespace_inject(
            "record_type"
        ) if override_config.record_type else None

        # Find existing override with same key fields
        existing_override = self._find_existing_override(metadata, override_config)

        if existing_override:
            self.logger.warning(
                f"Updating existing profileActionOverride for {override_config.profile}/{override_config.page_or_sobject_type}/{override_config.action_name} in {api_name}"
            )
            # Update the existing override
            self._update_override_element(
                existing_override,
                override_config,
            )
        else:
            self.logger.info(
                f"Adding profileActionOverride for {override_config.profile}/{override_config.page_or_sobject_type}/{override_config.action_name} to {api_name}"
            )
            # Create new override
            self._create_new_override(metadata, override_config)

    def _find_existing_override(self, metadata, override_config):
        """
        Find an existing profileActionOverride that matches the key fields:
        actionName, pageOrSobjectType, recordType, and profile
        """
        for override_elem in metadata.findall("profileActionOverrides"):
            elem_action = override_elem.find("actionName")
            elem_page = override_elem.find("pageOrSobjectType")
            elem_record_type = override_elem.find("recordType")
            elem_profile = override_elem.find("profile")

            # Match on all key fields
            if (
                elem_action
                and elem_action.text == override_config.action_name
                and elem_page
                and elem_page.text == override_config.page_or_sobject_type
                and elem_profile
                and elem_profile.text == override_config.profile
            ):
                # Handle recordType - both must be None or both must match
                if override_config.record_type is None and elem_record_type is None:
                    return override_elem
                elif (
                    override_config.record_type is not None
                    and elem_record_type is not None
                    and elem_record_type.text == override_config.record_type
                ):
                    return override_elem

        return None

    def _update_override_element(
        self,
        override_elem,
        override_config,
    ):
        """Update an existing profileActionOverride element"""
        # Update each child element
        # actionName
        elem = override_elem.find("actionName")
        if elem is not None:
            elem.text = override_config.action_name

        # content
        elem = override_elem.find("content")
        if elem is not None:
            elem.text = override_config.content

        # formFactor
        elem = override_elem.find("formFactor")
        if elem is not None:
            elem.text = override_config.form_factor

        # pageOrSobjectType
        elem = override_elem.find("pageOrSobjectType")
        if elem is not None:
            elem.text = override_config.page_or_sobject_type

        # recordType (optional)
        elem = override_elem.find("recordType")
        if override_config.record_type:
            if elem is not None:
                elem.text = override_config.record_type
        elif elem is not None:
            # Remove recordType if it exists but shouldn't
            override_elem.remove(elem)

        # type
        elem = override_elem.find("type")
        if elem is not None:
            elem.text = override_config.type

        # profile
        elem = override_elem.find("profile")
        if elem is not None:
            elem.text = override_config.profile

    def _create_new_override(
        self,
        metadata,
        override_config,
    ):
        """Create a new profileActionOverride element with proper ordering"""
        override_elem = metadata.append("profileActionOverrides")

        # Add elements in the correct order per Salesforce metadata API
        override_elem.append("actionName", text=override_config.action_name)
        override_elem.append("content", text=override_config.content)
        override_elem.append("formFactor", text=override_config.form_factor)
        override_elem.append(
            "pageOrSobjectType", text=override_config.page_or_sobject_type
        )

        # recordType is optional
        if override_config.record_type:
            override_elem.append("recordType", text=override_config.record_type)

        override_elem.append("type", text=override_config.type)
        override_elem.append("profile", text=override_config.profile)
