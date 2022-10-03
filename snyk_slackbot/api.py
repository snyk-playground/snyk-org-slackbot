import json
import os

import snyk


class SnykApiFacade:
    def __init__(self, settings):
        token = os.environ[settings.config("snyk_token_env_var_name")]
        self.settings = settings
        self.client_ll = snyk.SnykClient(
            token, version="2022-08-12", url="https://api.snyk.io/api/v1"
        )
        self.client_hl = snyk.SnykClient(token)

    def create_organisation(self, name):
        """
        Will try and create a new Snyk organisation with the given name, under the group defined in the settings file
        :param name: the name of the org to create
        :return: Either the json response from the API, or False in the case of an error
        """
        try:
            return self.client_ll.post(
                "/org", {"name": name, "groupId": self.settings.config("snyk_group_id")}
            ).json()
        except Exception as e:
            return False

    def org_name_exists(self, name):
        """
        Because it's possible for multiple orgs to have the same name within Snyk, we must manually check to ensure that
        our org name isn't already in Snyk.
        :param name: the name of the org (generated from user input)
        :return: Truthy (org id) if the org already exists within our group, False otherwise
        """
        orgs = self.client_hl.organizations.filter(
            name=name
        )  # TODO: Filter by group ID here too
        if len(orgs) > 0:
            return [x.id for x in orgs]
        else:
            return False

    def get_user(self, email_address):
        """
        Gets the specified user from the Snyk group
        :param group_id: the group we're working with
        :param email_address: the email address of the user to lookup
        :return: a dict of the user if found, None otherwise
        """
        try:
            result = self.client_ll.get(
                f"/group/{self.settings.config('snyk_group_id')}/members"
            ).json()
            for user in result:
                print(user["email"])
                if user["email"] == email_address:
                    return user
        except Exception as e:
            return None
        return None

    def add_user_to_org(self, org_id, user_id):
        """
        Will add a user to the specified organisation
        :param group_id: the group ID within Snyk
        :param org_id: the org ID we want to add the user to
        :param user_id: the user ID in Snyk of the user we wish to add
        :param role: the role we'll assign the user (default: admin)
        :return: True if addition was successful, False otherwise
        """
        try:
            result = self.client_ll.post(
                f"/group/{self.settings.config('snyk_group_id')}/org/{org_id}/members",
                {"userId": user_id, "role": "admin"},
            ).json()
            return True
        except Exception as e:
            return False

    def get_org_from_name(self, org_name):
        """
        Looks up an org by its name in Snyk and returns the org ID
        :param org_name: the org ID to look for
        :return: the org id, or None if we weren't successful
        """
        try:
            found_org = self.client_hl.organizations.filter(name=org_name)[0]
            return found_org
        except Exception as e:
            return None

    def get_org_admins(self, org):
        """
        Returns a list of org admins
        :param org: the org object
        :return: a list of org admins
        """
        return org.members.filter(role="admin")
