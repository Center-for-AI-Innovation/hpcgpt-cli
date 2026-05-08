import logging
from typing import Any
from jira import JIRA
from jira.exceptions import JIRAError

log = logging.getLogger("JIRA_MCP_SERVER")

class JiraConnectionManager:
    def __init__(self, server_url: str, username: str = None, api_key: str = None, personal_access_token: str = None):
        self.connection = None
        self.server_url = server_url
        self.username = username
        self.api_key = api_key
        self.personal_access_token = personal_access_token

    def ready(self) -> bool:
        return self.connection is not None

    def connect(self, auth_method: str = "personal_access_token") -> JIRA:
        if auth_method not in ["personal_access_token", "username_api_key"]:
            raise ValueError("Invalid authentication method. Must be 'personal_access_token' or 'username_api_key'")
        
        if auth_method == "personal_access_token":
            if self.personal_access_token is None:
                raise ValueError("Personal access token is required to connect to Jira")
            header = {'Authorization': f'Bearer {self.personal_access_token}'}
            log.info(f"Authenticating with personal access token to Jira Server at {self.server_url}")
        elif auth_method == "username_api_key":
            if self.username is None or self.api_key is None:
                raise ValueError("Username and API key are required to connect to Jira")
            header = {'Authorization': f'Basic {self.username}:{self.api_key}'}
            log.info(f"Authenticating with username and API key to Jira Server at {self.server_url}")

        self.connection = JIRA(server=self.server_url, options={'headers': header})
        log.info("Successfully connected to Jira server")
        return 0

    def get_custom_field_ids(self, project: str, issue_type: str) -> dict:
        """
        Helper function to find custom field IDs for a project.
        Uses Jira 10+ compatible API methods (project_issue_types and project_issue_fields).
        
        Args:
            project (str): The project to get custom field ids from. This should be a JIRA project key.
            issue_type (str): The issue type to get fields for.
        
        Returns:
            dict: Dictionary mapping field names to field IDs
        """
        if self.connection is None:
            raise ValueError("Connection to Jira is required. Call connect() first.")
        
        # Get issue types for the project
        log.debug(f"Getting issue types for project {project}")
        issue_types = self.connection.project_issue_types(project=project)
            
        if not issue_types:
            raise ValueError(f"No issue types found for project {project}.")
        if issue_type not in [it.name for it in issue_types]:
            raise ValueError(f"Issue type '{issue_type}' not found in project {project}. Available issue types are: {', '.join([it.name for it in issue_types])}")

        # Get available fields for the issue type
        target_issue_type = next(it for it in issue_types if it.name == issue_type)
        log.debug(f"Getting fields for Project {project}, Issue Type {issue_type}")
        fields = self.connection.project_issue_fields(project=project, issue_type=target_issue_type.id)
        log.debug(f"Fields for Project {project}, Issue Type {issue_type}:")
        field_dict = {}
        for field in fields:
            log.debug(f"  - {field.name} (ID: {field})")
            field_dict[field.name] = str(field)
        return field_dict

    def find_user(self, email: str = None, username: str = None) -> dict:
        """
        Find a Jira user by email, username, or both and return normalized identity fields.

        Returns:
            dict: {
                "display_name": str | None,
                "email": str | None,
                "name": str | None,
                "key": str | None,
                "account_id": str | None,
                "reporter_field": dict
            }
            The reporter_field is ready to use in create_issue:
            - {"accountId": "..."} on Jira Cloud
            - {"name": "..."} or {"key": "..."} on Jira Server/DC
        """
        if self.connection is None:
            raise ValueError("Connection to Jira is required. Call connect() first.")
        normalized_email = email.strip().lower() if email and email.strip() else None
        normalized_username = username.strip().lower() if username and username.strip() else None
        if normalized_email is None and normalized_username is None:
            raise ValueError("Email or username is required")

        def _search_term(term: str) -> list[Any]:
            users_for_term = []
            # python-jira versions differ on query parameter names.
            for kwargs in ({"query": term, "maxResults": 50}, {"user": term, "maxResults": 50}, {"username": term, "maxResults": 50}):
                try:
                    users_for_term = self.connection.search_users(**kwargs) or []
                    if users_for_term:
                        break
                except (TypeError, JIRAError) as err:
                    log.debug("search_users failed for term=%s params=%s: %s", term, kwargs, err)
                    continue
            return users_for_term

        candidates: list[Any] = []
        if normalized_email:
            email_users = _search_term(normalized_email)
            log.debug("Users found for email %s: %s", normalized_email, email_users)
            candidates.extend(email_users)
        if normalized_username:
            username_users = _search_term(normalized_username)
            log.debug("Users found for username %s: %s", normalized_username, username_users)
            candidates.extend(username_users)

        if not candidates:
            wanted = ", ".join(
                part for part in [
                    f"email={normalized_email}" if normalized_email else "",
                    f"username={normalized_username}" if normalized_username else "",
                ] if part
            )
            raise ValueError(f"No Jira user found for {wanted}")

        # De-duplicate candidates by stable identity.
        users_by_id: dict[str, Any] = {}
        for u in candidates:
            ident = (
                str(getattr(u, "accountId", "") or "").strip()
                or str(getattr(u, "name", "") or "").strip()
                or str(getattr(u, "key", "") or "").strip()
                or str(getattr(u, "displayName", "") or "").strip()
            )
            if ident:
                users_by_id[ident] = u
        users = list(users_by_id.values()) or candidates

        def _email_matches(u: Any) -> bool:
            if not normalized_email:
                return True
            return str(getattr(u, "emailAddress", "") or "").lower() == normalized_email

        def _username_matches(u: Any) -> bool:
            if not normalized_username:
                return True
            user_name = str(getattr(u, "name", "") or "").lower()
            user_key = str(getattr(u, "key", "") or "").lower()
            return normalized_username in {user_name, user_key}

        # If both are provided, prefer candidates that match both.
        exact_both = [u for u in users if _email_matches(u) and _username_matches(u)]
        if exact_both:
            chosen_user = exact_both[0]
        elif normalized_email:
            exact_email = [u for u in users if _email_matches(u)]
            chosen_user = exact_email[0] if exact_email else users[0]
        else:
            exact_username = [u for u in users if _username_matches(u)]
            chosen_user = exact_username[0] if exact_username else users[0]

        account_id = getattr(chosen_user, "accountId", None)
        username = getattr(chosen_user, "name", None)
        user_key = getattr(chosen_user, "key", None)

        if account_id:
            reporter_field = {"accountId": account_id}
        elif username:
            reporter_field = {"name": username}
        elif user_key:
            reporter_field = {"key": user_key}
        else:
            raise ValueError(
                f"Found user for email={normalized_email} username={normalized_username}, but no usable accountId/name/key was returned"
            )

        result = {
            "display_name": getattr(chosen_user, "displayName", None),
            "email": getattr(chosen_user, "emailAddress", None),
            "name": username,
            "key": user_key,
            "account_id": account_id,
            "reporter_field": reporter_field,
        }
        log.info(
            "Matched Jira user for email=%s username=%s: display_name=%s reporter_field=%s",
            normalized_email,
            normalized_username,
            result["display_name"],
            reporter_field,
        )
        return result

    def find_user_by_email(self, email: str) -> dict:
        """Backward-compatible wrapper for email-only lookup."""
        return self.find_user(email=email)

    def create_issue(self, project: str, issue_type: str, reporter: str, summary: str, description: str, fields: dict = None) -> dict:
        """
        Create a Jira issue in the JIRA project with fields.
        The fields are set in the jira.cfg file.
        Args:
            summary (str): The summary/title of the issue (required)
            description (str): Detailed description of the issue

        Returns:
            dict: Dictionary containing issue information including key, id, and URL
        """
        # Pre-checks
        if self.connection is None:
            raise ValueError("Connection to Jira is required to create an issue")

        # Add required fields to the issue dict
        issue_dict = {
            'project': {'key': project},
            'issuetype': {'name': issue_type},
            'summary': summary,
            'description': description,
            'reporter': {'name': reporter},
        }
        try:
            issue = self.connection.create_issue(fields=issue_dict)
            issue_url = f"{self.server_url}/browse/{issue.key}"
            result = {
                'key': issue.key,
                'id': issue.id,
                'url': issue_url,
                'summary': issue.fields.summary,
                'status': issue.fields.status.name,
            }

            log.info(f"Successfully created issue: {result['key']} at {result['url']}")
        except Exception as e:
            log.error(f"Encountered error creating issue: {e}")

        # Set optional/default fields after issue creation.
        if fields:
            for field_name, field_value in fields.items():
                if field_name.lower() in ['project', 'summary', 'description', 'issuetype', 'reporter']:
                    log.warning(f"Cannot set a default field for {field_name}. Skipping.")
                    continue
                try:
                    self.set_issue_field(
                        issue_key=issue.key,
                        field_name=field_name,
                        field_value=field_value,
                        use_display_name=True,
                    )
                except Exception as e:
                    log.warning(f"Could not set field {field_name} on issue {issue.key}: {e}")
        return issue
        

    def add_comment(self,issue_key: str, comment: str, visibility: str = None) -> dict:
        """
        Add a comment to an existing Jira issue.
        
        Can be used to add an internal (staff-only) comment or a public comment.
        Internal comments are only visible to members of the specified group/role,
        not to external customers or all users.
        """
        
        try:
            # Get the issue to verify it exists
            issue = self.connection.issue(issue_key)
            
            # Set visibility parameter
            if visibility is not None:
                visibility_dict = {'type': "role", 'value': visibility}
            else:
                visibility_dict = None

            comment = self.connection.add_comment(issue=issue_key, body=comment, visibility=visibility_dict)
            
            # Get comment details
            result = {
                'id': comment.id,
                'author': comment.author.displayName if hasattr(comment.author, 'displayName') else str(comment.author),
                'created': comment.created,
                'body': comment.body,
                'visibility': {'type': visibility_dict['type'],'value': visibility_dict['value']},
                'issue_key': issue_key,
                'issue_url': f"{self.server_url}/browse/{issue_key}"
            }
            
            log.info(f"Successfully added comment to {issue_key}")
            log.info(f"  Comment ID: {comment.id}")
            log.info(f"  Visibility: {visibility_dict['value']} ({visibility_dict['type']}) only")
            log.info(f"  Issue URL: {result['issue_url']}")
            
            return result
        
        except Exception as e:
            error_msg = f"Error adding comment to {issue_key}: {e}"
            log.error(error_msg)
            raise Exception(error_msg) from e

    def get_projects(self) -> list:
        """
        Get all projects from Jira.
        """
        if self.connection is None:
            raise ValueError("Connection to Jira is required to get projects")
        projects = self.connection.projects()
        for project in projects:
            log.info(f"  - Project Name: {project.name}, Key: {project.key}")
        return projects

    def set_issue_field(self, issue_key: str, field_name: str, field_value: Any, use_display_name: bool = True) -> dict[str, Any]:
        """
        Set a single field on an existing Jira issue.
        Args:
            issue_key: Jira issue key (e.g. "CMAAS-123")
            field_name: Jira field key/id (e.g. "labels", "customfield_12345") or
                display name (e.g. "Labels", "Priority") if use_display_name=True.
            field_value: Value to set for the field.
            use_display_name: Attempt to resolve display name to a Jira field id/key.

        Returns:
            Dict describing the applied update.
        """
        if self.connection is None:
            raise ValueError("Connection to Jira is required. Call connect() first.")
        if not issue_key or not issue_key.strip():
            raise ValueError("issue_key is required")
        if not field_name or not field_name.strip():
            raise ValueError("field_name is required")

        issue_key = issue_key.strip()
        raw_field_name = field_name.strip()
        resolved_field_key = raw_field_name

        if use_display_name:
            try:
                # Map display names ("Priority") to API keys/ids ("priority", "customfield_...").
                known_fields = self.connection.fields() or []
                fields_by_name = {
                    str(f.get("name", "")).strip().lower(): f.get("id")
                    for f in known_fields
                    if f.get("name") and f.get("id")
                }
                resolved_field_key = fields_by_name.get(raw_field_name.lower(), raw_field_name)
            except Exception as e:
                log.debug(
                    "Could not resolve field display name '%s'; using as-is (%s)",
                    raw_field_name,
                    e,
                )

        issue = self.connection.issue(issue_key)
        issue.update(fields={resolved_field_key: field_value})

        result = {
            "issue_key": issue_key,
            "field_name": raw_field_name,
            "resolved_field_key": resolved_field_key,
            "updated": True,
        }
        log.info(
            "Updated issue %s field %s (resolved as %s)",
            issue_key,
            raw_field_name,
            resolved_field_key,
        )
        return result

    