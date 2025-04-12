import cumulusci.core.azure_devops as scm
from cumulusci.core.tasks import BaseScmTask


class BaseAzureTask(BaseScmTask):
    def _init_task(self):
        super()._init_task()

        # Set azure variables
        self.azure_config = self.project_config.keychain.get_service("azure_devops")
        self.azure_connection = scm.get_azure_api_conntection(self.azure_config)
        self.azure_core_client = self.azure_connection.clients.get_core_client()
        self.azure_git_client = self.azure_connection.clients.get_git_client()

    def get_tag_by_name(self):
        src_tag_name = self.options["src_tag"]
        refs = self.git_client.get_refs(
            self.repo.id, self.repo.project.id, filter=f"tags/{src_tag_name}"
        )
        if len(refs) == 1:
            return refs[0]

    def create_tag(self):
        src_tag_name = self.options["src_tag"]

        # TODO: Identify the repo name and project name of Azure.
        self.repo = self.azure_git_client.get_repository(
            self.project_config.repo_name, self.project_config.repo_name
        )

        src_tag = self.get_tag_by_name()

        tag = None

        if src_tag is not None:

            from importlib import import_module

            module_parts = self.git_client.__class__.__module__.split(".")[:-1]
            models = import_module(".".join(module_parts), "models")

            clone_tag = models.GitAnnotatedTag()
            clone_tag.message = f"Cloned from {src_tag_name}"
            clone_tag.name = self.options["tag"]

            clone_tag.tagged_object = models.GitObject()
            clone_tag.tagged_object.object_id = src_tag.object_id

            tag = self.git_client.create_annotated_tag(
                clone_tag, self.repo.project.id, self.repo.id
            )

        return tag

    def gather_release_notes(self):
        table_of_contents = "<h1>Table of Contents</h1><ul>"
        body = ""
        for project in self.options["repos"]:
            if project["owner"] and project["repo"]:
                release = (
                    self.github.repository(project["owner"], project["repo"])
                    .latest_release()
                    .body
                )
                table_of_contents += (
                    f"""<li><a href="#{project['repo']}">{project['repo']}</a></li>"""
                )
                release_project_header = (
                    f"""<h1 id="{project['repo']}">{project['repo']}</h1>"""
                )
                release_html = self.github.markdown(
                    release,
                    mode="gfm",
                    context="{}/{}".format(project["owner"], project["repo"]),
                )
                body += f"{release_project_header}<hr>{release_html}<hr>"
        table_of_contents += "</ul><br><hr>"
        head = "<head><title>Release Notes</title></head>"
        body = f"<body>{table_of_contents}{body}</body>"
        result = f"<html>{head}{body}</html>"
        with open("github_release_notes.html", "w") as f:
            f.write(result)

    def get_version_id_from_tag(self, tag_name):
        self.logger.info(
            f"get_version_id_from_tag from Azure module called for tag {tag_name}"
        )
        # return scm.get_version_id_from_tag(repo, tag_name)
