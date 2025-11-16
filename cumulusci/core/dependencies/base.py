import contextlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Type
from zipfile import ZipFile

from pydantic.v1 import AnyUrl, PrivateAttr, root_validator, validator

from cumulusci.core.config import OrgConfig
from cumulusci.core.config.project_config import BaseProjectConfig
from cumulusci.core.dependencies.utils import TaskContext
from cumulusci.core.exceptions import DependencyResolutionError, VcsNotFoundError
from cumulusci.core.flowrunner import (
    FlowCallback,
    FlowCoordinator,
    StepResult,
    StepVersion,
)
from cumulusci.core.sfdx import (
    SourceFormat,
    convert_sfdx_source,
    get_source_format_for_zipfile,
)
from cumulusci.core.utils import format_duration
from cumulusci.salesforce_api.metadata import ApiDeploy
from cumulusci.salesforce_api.package_zip import MetadataPackageZipBuilder
from cumulusci.utils import (
    download_extract_vcs_from_repo,
    get_tasks_with_options,
    temporary_dir,
)
from cumulusci.utils.yaml.model_parser import HashableBaseModel
from cumulusci.utils.ziputils import zip_subfolder
from cumulusci.vcs.models import AbstractRepo


class DependencyPin(HashableBaseModel, ABC):
    @abstractmethod
    def can_pin(self, d: "DynamicDependency") -> bool:
        raise NotImplementedError("Subclasses must implement can_pin.")

    @abstractmethod
    def pin(self, d: "DynamicDependency", context: BaseProjectConfig):
        raise NotImplementedError("Subclasses must implement pin.")


DependencyPin.update_forward_refs()


class VcsDependencyPin(DependencyPin):
    url: Optional[AnyUrl] = None
    tag: str

    @property
    @abstractmethod
    def vcsTagResolver(self):  # -> Type["AbstractTagResolver"]:
        raise NotImplementedError("Subclasses must implement vcsTagResolver.")

    @root_validator(pre=True)
    @abstractmethod
    def sync_vcs_and_url(cls, values):
        """Defined vcs should be assigned to url"""
        raise NotImplementedError("Subclasses must implement sync_vcs_and_url.")

    def can_pin(self, d: "DynamicDependency") -> bool:
        return isinstance(d, BaseVcsDynamicDependency) and d.url == self.url

    def pin(self, d: "BaseVcsDynamicDependency", context: BaseProjectConfig):
        if d.tag and d.tag != self.tag:
            raise DependencyResolutionError(
                f"A pin is specified for {self.url}, but the dependency already has a tag specified."
            )
        d.tag = self.tag
        d.ref, d.package_dependency = self.vcsTagResolver().resolve(d, context)


class Dependency(HashableBaseModel, ABC):
    """Abstract base class for models representing dependencies

    Dependencies can be _resolved_ to an immutable version, or not.
    They can also be _flattened_ (turned into a list including their own transitive dependencies) or not.
    """

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    def description(self):
        return self.name

    @property
    @abstractmethod
    def is_resolved(self):
        return False

    @property
    @abstractmethod
    def is_flattened(self):
        return False

    def flatten(self, context: BaseProjectConfig) -> List["Dependency"]:
        """Get a list including this dependency as well as its transitive dependencies."""
        return [self]

    def __str__(self):
        return self.description


Dependency.update_forward_refs()


class StaticDependency(Dependency, ABC):
    """Abstract base class for dependencies that we know how to install (i.e., they
    are already both resolved and flattened)."""

    @abstractmethod
    def install(self, org_config: OrgConfig, retry_options: Optional[dict] = None):
        pass

    @property
    def is_resolved(self):
        return True

    @property
    def is_flattened(self):
        return True


class DynamicDependency(Dependency, ABC):
    """Abstract base class for dependencies with dynamic references, like GitHub.
    These dependencies must be resolved and flattened before they can be installed."""

    url: Optional[AnyUrl] = None
    package_dependency: Optional[StaticDependency] = None
    password_env_name: Optional[str] = None

    @property
    def is_flattened(self):
        return False

    @root_validator(pre=True)
    @abstractmethod
    def sync_vcs_and_url(cls, values):
        """Defined vcs should be assigned to url"""
        raise NotImplementedError("Subclasses must implement sync_vcs_and_url.")

    def resolve(
        self,
        context: BaseProjectConfig,
        strategies: List,  # List[DependencyResolutionStrategy], but circular import
        pins: Optional[List[DependencyPin]] = None,
    ):
        """Resolve a DynamicDependency that is not pinned to a specific version into one that is."""
        # avoid import cycle
        from .resolvers import resolve_dependency

        for pin in pins or []:
            if pin.can_pin(self):
                context.logger.info(f"Pinning dependency {self} to {pin}")
                pin.pin(self, context)
                return

        resolve_dependency(self, context, strategies)


class UnmanagedStaticDependency(StaticDependency, ABC):
    unmanaged: Optional[bool] = None
    namespace_inject: Optional[str] = None
    namespace_strip: Optional[str] = None
    collision_check: Optional[bool] = None

    def _get_unmanaged(self, org: OrgConfig):
        if self.unmanaged is None:
            if self.namespace_inject:
                return self.namespace_inject not in org.installed_packages
            else:
                return True

        return self.unmanaged


class UnmanagedDependency(UnmanagedStaticDependency, ABC):
    """Abstract base class for static, unmanaged dependencies."""

    subfolder: Optional[str] = None

    @abstractmethod
    def _get_zip_src(self, context: BaseProjectConfig) -> ZipFile:
        pass

    def get_metadata_package_zip_builder(
        self, project_config: BaseProjectConfig, org: OrgConfig
    ) -> MetadataPackageZipBuilder:
        zip_src = self._get_zip_src(project_config)
        # Determine whether to inject namespace prefixes or not
        # If and only if we have no explicit configuration.

        options = {
            "unmanaged": self._get_unmanaged(org),
            "namespace_inject": self.namespace_inject,
            "namespace_strip": self.namespace_strip,
        }

        # We have a zip file. Now, determine how to handle
        # MDAPI/SFDX format, with or without a subfolder specified.

        # In only two cases do we need to do a zip subset.
        # Either we have a repo root in MDAPI format and need to get `src`,
        # or we're deploying a subfolder that is in MDAPI format.
        zip_extract_subfolder = None
        if (
            not self.subfolder
            and get_source_format_for_zipfile(zip_src, "src") is SourceFormat.MDAPI
        ):
            zip_extract_subfolder = "src"
        elif (
            self.subfolder
            and get_source_format_for_zipfile(zip_src, self.subfolder)
            is SourceFormat.MDAPI
        ):
            zip_extract_subfolder = self.subfolder

        if zip_extract_subfolder:
            zip_src = zip_subfolder(zip_src, zip_extract_subfolder)

        source_format = get_source_format_for_zipfile(
            zip_src, self.subfolder if not zip_extract_subfolder else None
        )

        real_path = None
        package_zip = None
        with contextlib.ExitStack() as stack:
            if source_format is SourceFormat.SFDX:
                # Convert source first.
                stack.enter_context(temporary_dir(chdir=True))
                zip_src.extractall()
                real_path = stack.enter_context(
                    convert_sfdx_source(self.subfolder, None, project_config.logger)
                )
                zip_src = None  # Don't use the zipfile if we converted source.

            context = TaskContext(org, project_config, project_config.logger)
            # We now know what to send to MetadataPackageZipBuilder
            # Note that subfolder logic is applied either by subsetting the zip
            # (for MDAPI) or by the conversion (for SFDX format)

            package_zip = MetadataPackageZipBuilder.from_zipfile(
                zip_src,
                path=real_path,
                options=options,
                context=context,
            )

        return package_zip

    def install(
        self, context: BaseProjectConfig, org: OrgConfig, options: Optional[dict] = {}
    ):

        context.logger.info(f"Deploying unmanaged metadata from {self.description}")

        package_zip_builder = self.get_metadata_package_zip_builder(context, org)
        task = TaskContext(
            org_config=org, project_config=context, logger=context.logger
        )
        api = ApiDeploy(task, package_zip_builder.as_base64())

        return api()


class BaseVcsDynamicDependency(DynamicDependency, ABC):
    """Abstract base class for dynamic dependencies that are stored in a VCS."""

    tag: Optional[str] = None
    ref: Optional[str] = None

    vcs: str = ""  # Need to validate presence of this pydantic field in subclasses
    _repo: Optional[AbstractRepo] = PrivateAttr(default=None)

    @property
    @abstractmethod
    def is_unmanaged(self):
        pass

    @property
    def is_resolved(self):
        return bool(self.ref)

    @property
    def repo(self):
        # if not self._repo:
        #     raise ValueError("VCS DynamicDependency has no repo set")
        return self._repo

    def set_repo(self, value: AbstractRepo):
        self._repo = value

    @root_validator
    def check_complete(cls, values):

        assert values["ref"] is None, "Must not specify `ref` at creation."
        return values

    @property
    def name(self):
        return f"Dependency: {self.url}"


class VcsDynamicSubfolderDependency(BaseVcsDynamicDependency, ABC):
    """A dependency expressed by a reference to a subfolder of a ADO repo, which needs
    to be resolved to a specific ref. This is always an unmanaged dependency."""

    subfolder: str
    namespace_inject: Optional[str] = None
    namespace_strip: Optional[str] = None

    @property
    def is_unmanaged(self):
        return True

    @property
    def name(self) -> str:
        return f"Dependency: {self.url}/{self.subfolder}"

    @property
    def description(self) -> str:
        loc = f" @{self.tag or self.ref}" if self.ref or self.tag else ""
        return f"{self.url}/{self.subfolder}{loc}"

    @property
    @abstractmethod
    def unmanagedVcsDependency(self) -> Type[UnmanagedDependency]:
        raise NotImplementedError("Subclasses must implement unmanagedVcsDependency.")

    def flatten(self, context: BaseProjectConfig) -> List[Dependency]:
        """Convert to a static dependency after resolution"""

        if not self.is_resolved:
            raise DependencyResolutionError(
                f"Dependency {self} is not resolved and cannot be flattened."
            )

        return [
            self.unmanagedVcsDependency(
                url=self.url,
                ref=self.ref or "",
                subfolder=self.subfolder,
                namespace_inject=self.namespace_inject,
                namespace_strip=self.namespace_strip,
            )
        ]


class VcsDynamicDependency(BaseVcsDynamicDependency, ABC):
    """A dependency expressed by a reference to a ADO repo, which needs
    to be resolved to a specific ref and/or package version."""

    unmanaged: bool = False
    namespace_inject: Optional[str] = None
    namespace_strip: Optional[str] = None
    password_env_name: Optional[str] = None

    skip: List[str] = []

    @property
    def is_unmanaged(self):
        return self.unmanaged

    @property
    @abstractmethod
    def unmanagedVcsDependency(self) -> Type[UnmanagedDependency]:
        raise NotImplementedError("Subclasses must implement unmanagedVcsDependency.")

    @abstractmethod
    def get_repo(self, context, url) -> AbstractRepo:
        raise NotImplementedError("Subclasses must implement get_repo.")

    @validator("skip", pre=True)
    def listify_skip(cls, v):
        if v and not isinstance(v, list):
            v = [v]
        return v

    @root_validator
    def check_unmanaged_values(cls, values):

        if not values.get("unmanaged") and (
            values.get("namespace_inject") or values.get("namespace_strip")
        ):
            raise ValueError(
                "The namespace_strip and namespace_inject fields require unmanaged = True"
            )

        return values

    def _flatten_dependency_flow(
        self,
        remote_config: BaseProjectConfig,
        flow_type: str,
        managed: bool,
        namespace: Optional[str],
    ) -> List[StaticDependency]:

        if remote_config.project.get(flow_type):
            return [
                UnmanagedVcsDependencyFlow(
                    url=self.url,
                    vcs=self.vcs,
                    commit=self.ref,
                    flow_name=remote_config.project.get(flow_type),
                    unmanaged=not managed,
                    namespace_inject=namespace if namespace and managed else None,
                    namespace_strip=namespace if namespace and not managed else None,
                    package_dependency=self.package_dependency,
                )
            ]
        return []

    def _flatten_unpackaged(
        self,
        repo: AbstractRepo,
        subfolder: str,
        skip: List[str],
        managed: bool,
        namespace: Optional[str],
    ) -> List[StaticDependency]:
        """Locate unmanaged dependencies from a repository subfolder (such as unpackaged/pre or unpackaged/post)"""
        unpackaged = []
        try:
            contents = repo.directory_contents(subfolder, return_as=dict, ref=self.ref)
        except VcsNotFoundError:
            contents = None

        if contents:
            for dirname in sorted(contents.keys()):
                this_subfolder = f"{subfolder}/{dirname}"
                if this_subfolder in skip:
                    continue

                unpackaged.append(
                    self.unmanagedVcsDependency(
                        url=self.url,
                        ref=self.ref,
                        subfolder=this_subfolder,
                        unmanaged=not managed,
                        namespace_inject=namespace if namespace and managed else None,
                        namespace_strip=namespace
                        if namespace and not managed
                        else None,
                        package_dependency=self.package_dependency,
                    )
                )

        return unpackaged

    def flatten(self, context: BaseProjectConfig) -> List[Dependency]:
        """Find more dependencies based on repository contents.

        Includes:
        - dependencies from cumulusci.yml
        - subfolders of unpackaged/pre
        - the contents of src, if this is not a managed package
        - subfolders of unpackaged/post
        """
        from cumulusci.core.dependencies.dependencies import parse_dependency
        from cumulusci.core.dependencies.resolvers import get_package_data
        from cumulusci.vcs.bootstrap import get_remote_project_config

        if not self.is_resolved:
            raise DependencyResolutionError(
                f"Dependency {self} is not resolved and cannot be flattened."
            )

        deps = []

        context.logger.info(f"Collecting dependencies from {self.vcs} repo {self.url}")
        repo = self.get_repo(context, self.url)

        package_config = get_remote_project_config(repo, self.ref)
        _, namespace = get_package_data(package_config)

        # Parse upstream dependencies from the repo's cumulusci.yml
        # These may be unresolved or unflattened; if so, `get_static_dependencies()`
        # will manage them.
        dependencies = package_config.project__dependencies
        if dependencies:
            deps.extend([parse_dependency(d) for d in dependencies])
            if None in deps:
                raise DependencyResolutionError(
                    f"Unable to flatten dependency {self} because a transitive dependency could not be parsed."
                )

        # Check for unmanaged flag on a namespaced package
        managed = bool(namespace and not self.unmanaged)

        # Look for any flow to executed in project config
        # Pre flows will run to dynamically generate metadata and deploy.
        flow = self._flatten_dependency_flow(
            package_config,
            "dependency_flow_pre",
            managed=False,
            namespace=namespace,
        )
        if flow:
            deps.extend(flow)
        else:
            # Look for subfolders under unpackaged/pre
            # unpackaged/pre is always deployed unmanaged, no namespace manipulation.
            deps.extend(
                self._flatten_unpackaged(
                    repo, "unpackaged/pre", self.skip, managed=False, namespace=None
                )
            )

        if not self.package_dependency:
            if managed:
                # We had an expectation of finding a package version and did not.
                raise DependencyResolutionError(
                    f"Could not find latest release for {self}"
                )

            # Deploy the project, if unmanaged.
            deps.append(
                self.unmanagedVcsDependency(
                    url=self.url,
                    ref=self.ref,
                    unmanaged=self.unmanaged,
                    namespace_inject=self.namespace_inject,
                    namespace_strip=self.namespace_strip,
                )
            )
        else:
            deps.append(self.package_dependency)

        # Look for any flow to executed in project config
        # Pre flows will run to dynamically generate metadata and deploy.
        flow = self._flatten_dependency_flow(
            package_config,
            "dependency_flow_post",
            managed=managed,
            namespace=namespace,
        )

        if flow:
            deps.extend(flow)
        else:
            # We always inject the project's namespace into unpackaged/post metadata if managed
            deps.extend(
                self._flatten_unpackaged(
                    repo,
                    "unpackaged/post",
                    self.skip,
                    managed=managed,
                    namespace=namespace,
                )
            )

        return deps

    @property
    def description(self):
        unmanaged = " (unmanaged)" if self.unmanaged else ""
        loc = f" @{self.tag or self.ref}" if self.ref or self.tag else ""
        return f"{self.url}{unmanaged}{loc}"


class UnmanagedVcsDependency(UnmanagedDependency, ABC):
    url: Optional[AnyUrl] = None
    ref: str

    # for backwards compatibility only; currently unused
    filename_token: Optional[str] = None
    namespace_token: Optional[str] = None

    # Add these fields to support subfolder and namespace manipulation
    subfolder: Optional[str] = None
    namespace_inject: Optional[str] = None
    namespace_strip: Optional[str] = None

    # Field to reference corresponding package dependency
    package_dependency: Optional["BasePackageVersionDependency"] = None

    @root_validator(pre=True)
    @abstractmethod
    def sync_vcs_and_url(cls, values):
        """Defined vcs should be assigned to url"""
        raise NotImplementedError("Subclasses must implement sync_vcs_and_url.")

    @abstractmethod
    def get_repo(self, url, context) -> AbstractRepo:
        raise NotImplementedError("Subclasses must implement get_repo.")

    @property
    @abstractmethod
    def package_name(self) -> str:
        """A human-readable name of the dependency."""
        raise NotImplementedError("Subclasses must implement package_name.")

    def _get_zip_src(self, context):
        repo = self.get_repo(context, self.url)

        # We don't pass `subfolder` to download_extract_vcs_from_repo()
        # because we need to get the whole ref in order to
        # correctly handle any permutation of MDAPI/SFDX format,
        # with or without a subfolder specified.

        # install() will take care of that for us.
        return download_extract_vcs_from_repo(
            repo,
            ref=self.ref,
        )

    @property
    def name(self):
        subfolder = (
            f"/{self.subfolder}" if self.subfolder and self.subfolder != "src" else ""
        )
        return f"Deploy {self.url}{subfolder}"

    @property
    def description(self):
        subfolder = (
            f"/{self.subfolder}" if self.subfolder and self.subfolder != "src" else ""
        )

        return f"{self.url}{subfolder} @{self.ref}"

    def install(
        self, context: BaseProjectConfig, org: OrgConfig, options: Optional[dict] = {}
    ):
        if (
            self.package_dependency is not None
            and not self.package_dependency.is_installable(org, options)
        ):
            context.logger.info(
                f"{self.description} or a newer version is already deployed; skipping."
            )
            return
        super().install(context, org)


class UnmanagedVcsDependencyFlow(UnmanagedStaticDependency, ABC):
    vcs: str
    url: AnyUrl
    commit: str
    flow_name: str
    callback_class = FlowCallback

    # Add these fields to support namespace manipulation
    namespace_inject: Optional[str] = None
    namespace_strip: Optional[str] = None
    password_env_name: Optional[str] = None

    # Field to reference corresponding package dependency
    package_dependency: Optional["BasePackageVersionDependency"] = None

    @property
    def name(self):
        return f"Deploy {self.url} Flow: {self.flow_name}"

    @property
    def description(self):
        return f"{self.url} Flow: {self.flow_name} @{self.commit}"

    def install(
        self, context: BaseProjectConfig, org: OrgConfig, options: Optional[dict] = {}
    ):
        if (
            self.package_dependency is not None
            and not self.package_dependency.is_installable(org, options)
        ):
            context.logger.info(
                f"{self.description} or a newer version is already deployed; skipping."
            )
            return

        context.logger.info(f"Deploying dependency Flow from {self.description}")

        from cumulusci.utils.yaml.cumulusci_yml import VCSSourceModel
        from cumulusci.vcs.vcs_source import VCSSource

        # Get the VCS Source class from the vcs field.
        source_model = VCSSourceModel(
            vcs=self.vcs,
            url=self.url,
            commit=self.commit,
            allow_remote_code=context.allow_remote_code,
        )
        vcs_source = VCSSource.create(context, source_model)

        # Fetch the data and get remote project config.
        project_config = vcs_source.fetch()

        project_config.set_keychain(context.keychain)
        project_config.source = vcs_source

        # If I can't load remote code, make sure that my
        # included repos can't either.
        if vcs_source.allow_remote_code:
            project_config._add_tasks_directory_to_python_path()

        # Run the flow.
        flow_config = project_config.get_flow(self.flow_name)
        flow_config.name = self.flow_name

        managed = not self._get_unmanaged(org)

        pre_post_options = {
            "unmanaged": not managed,
            "managed": managed,
            "namespace_inject": self.namespace_inject,
            "namespace_strip": self.namespace_strip,
        }

        coordinator_opts = get_tasks_with_options(
            project_config, frozenset(pre_post_options.items())
        )

        coordinator = FlowCoordinator(
            project_config,
            flow_config,
            name=flow_config.name,
            options=coordinator_opts,
            skip=None,
            callbacks=self.callback_class(),
        )

        coordinator.results.append(
            StepResult(
                step_num=StepVersion("0.0.0"),
                task_name="flow",
                path=f"{self.flow_name}.flow",
                result=None,
                return_values=pre_post_options,
                exception=None,
            )
        )

        start_time = datetime.now()
        coordinator.run(org)
        duration = datetime.now() - start_time
        context.logger.info(f"Ran {self.flow_name} in {format_duration(duration)}")


class BasePackageVersionDependency(StaticDependency, ABC):
    @abstractmethod
    def is_installable(self, org: OrgConfig, options: Optional[dict] = {}) -> bool:
        pass


UnmanagedVcsDependency.update_forward_refs()
UnmanagedVcsDependencyFlow.update_forward_refs()
