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

    def create_tag(self):
        self.repo = self.azure_git_client.get_repository(
            self.project_config.repo_name, self.project_config.repo_project_name
        )

        src_tag = scm.get_tag_by_name(
            self.azure_git_client, self.repo, self.options["src_tag"]
        )
        tag = scm.clone_tag(
            self.azure_git_client, self.repo, src_tag, self.options["tag"]
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
