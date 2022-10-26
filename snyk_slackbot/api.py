import logging
import os

import snyk

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", default="INFO"))


def get_org_admins(org):
    """
    Returns a list of org admins
    :param org: the org object
    :return: a list of org admins
    """
    logger.debug("Getting list of admins from %s", org.name)
    return org.members.filter(role="admin")


class SnykApiFacade:
    def __init__(self, settings):
        token = os.getenv(settings.config("snyk_token_env_var_name"))
        self.settings = settings
        self.client_ll = snyk.SnykClient(
            token, version="2022-08-12", url="https://api.snyk.io/api/v1"
        )
        self.client_hl = snyk.SnykClient(token)

    def create_organisation(self, name):
        """
        Will try and create a new Snyk organisation with the given name, under the group defined
        in the settings file
        :param name: the name of the org to create
        :return: Either the json response from the API, or False in the case of an error
        """
        try:
            return self.client_ll.post(
                "/org", {"name": name, "groupId": self.settings.config("snyk_group_id")}
            ).json()
        except Exception as error:
            logger.error(
                "Unable to create organisation, API call threw error %s", str(error)
            )
            return False

    def org_name_exists(self, name):
        """
        Because it's possible for multiple orgs to have the same name within Snyk, we must manually
         check to ensure that
        our org name isn't already in Snyk.
        :param name: the name of the org (generated from user input)
        :return: Truthy (org id) if the org already exists within our group, False otherwise
        """
        logger.debug("Checking if org %s already exists", name)
        orgs = self.client_hl.organizations.filter(
            name=name
        )  # TODO: Filter by group ID here too
        if orgs:
            return [x.id for x in orgs]
        return False

    def get_user(self, email_address):
        """
        Gets the specified user from the Snyk group
        :param group_id: the group we're working with
        :param email_address: the email address of the user to lookup
        :return: a dict of the user if found, None otherwise
        """
        try:
            logger.debug("Checking if user %s exists in Snyk", email_address)
            result = self.client_ll.get(
                f"/group/{self.settings.config('snyk_group_id')}/members"
            ).json()
            for user in result:
                if user.get("email") == email_address:
                    return user
        except Exception as error:
            logger.error(
                "Error checking if user %s exists in Snyk - API threw error %s",
                email_address,
                str(error),
            )
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
            logger.debug("Adding user %s to org %s", user_id, org_id)
            self.client_ll.post(
                f"/group/{self.settings.config('snyk_group_id')}/org/{org_id}/members",
                {"userId": user_id, "role": "admin"},
            ).json()
            return True
        except Exception as error:
            logger.error(
                "Error adding user %s to org %s - API threw error %s",
                user_id,
                org_id,
                str(error),
            )
        return False

    def get_org_from_name(self, org_name):
        """
        Looks up an org by its name in Snyk and returns the org ID
        :param org_name: the org ID to look for
        :return: the org id, or None if we weren't successful
        """
        try:
            logger.debug("Looking up org %s by name", org_name)
            found_org = self.client_hl.organizations.filter(name=org_name)[0]
            return found_org
        except Exception as error:
            logger.error(
                "Error getting org %s by name - API threw error %s",
                org_name,
                str(error),
            )
        return None
