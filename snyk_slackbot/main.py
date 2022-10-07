import glob
import json
import logging
import os
import re

import yaml
from api import SnykApiFacade
from jinja2 import BaseLoader, Environment, FileSystemLoader
from settings import Settings
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

TEMPLATE_DIR = "./templates"
MESSAGE_TEMPLATE_DIR = f"{TEMPLATE_DIR}/messages"
SETTINGS_FILE = os.getenv("SETTINGS_FILE_PATH", "/opt/settings.yaml")

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", default="INFO"))
# Load settings from a file
settings = Settings.from_file(SETTINGS_FILE)
# In memory persistence
channel_datastore = {}
# Set up our API facade
api = SnykApiFacade(settings)
# Set up our Slack app
app = App(token=os.getenv("slack_bot_token_env_var_name"))
# Set up our regex matching patterns
business_unit_pattern = re.compile(settings.config("business_unit_regex_pattern"))
team_name_pattern = re.compile(settings.config("team_name_regex_pattern"))
# SSO params
sso_provider_name = settings.config("sso_provider_name")
sso_provider_link = settings.config("sso_sign_in_link")
# Commands
command_create_org = settings.config("command_create_org")
# Jinja2 environment
environment = Environment(loader=FileSystemLoader("./templates/"))
# Chat template messages
chat_messages = None


def load_blocks_views(view_name, **kwargs):
    """
    Will load a view, template it with the args given and return a python object
    :param view_name: the name of the view (file name without .json)
    :param kwargs: kwargs
    :return: python object representation of the view
    """
    template = environment.get_template(f"{view_name}.json")
    str_output = template.render(kwargs)
    return json.loads(str_output)


def load_chat_message_templates():
    """
    Loads chat messages from templates
    :return: dict representation of the chat messages
    """
    msgs = {}
    for template in glob.glob(f"{MESSAGE_TEMPLATE_DIR}/*.yaml"):
        template_key = os.path.splitext(template)[0].split("/")[-1]
        logger.info(f"Loaded chat template {template_key}")
        with open(template, "r") as file:
            yaml_data = yaml.safe_load(file)
            msgs[template_key] = yaml_data
    return msgs


def get_chat_message(template, key, **kwargs):
    """
    Will get a chat message template and template it with the given kwargs
    :param template: the main template name
    :param key: the key within the template
    :param kwargs: kwargs
    :return: templated string
    """
    message = chat_messages.get(template, {}).get(key)
    if message:
        str_environment = Environment(loader=BaseLoader).from_string(message)
        return str_environment.render(kwargs)
    return None


@app.command(f"/{command_create_org}")
def create_org_modal(ack, body, client):
    """
    Shows the initial modal for org creation (user input screen)
    :param ack: slack ack
    :param body: slack body
    :param client: slack client
    """
    logger.info("Received %s command - showing modal dialog.." % command_create_org)
    ack()
    client.views_open(
        trigger_id=body["trigger_id"], view=load_blocks_views("views/create_org_modal")
    )


@app.view("create_org_callback")
def create_org_callback(ack, body, client, say):
    """
    Handles when the user clicks the submit button the modal
    :param ack: slack ack
    :param body: slack body
    :param client: slack client
    :param say: slack say
    """
    ack()
    requesting_user = body["user"]
    requesting_user_email = app.client.users_info(user=requesting_user["id"])["user"][
        "profile"
    ]["email"]
    snyk_user = api.get_user(requesting_user_email)
    view_state = body["view"]["state"]
    logger.info(
        "%s submitted org creation modal dialog, opening DM channel" % requesting_user
    )

    # Let's open a DM channel with the requesting user
    conversation = client.conversations_open(users=requesting_user["id"])
    channel_id = conversation["channel"]["id"]

    # Extract the input from the modal output
    business_unit = view_state["values"]["block_business_unit"]["input_business_unit"][
        "value"
    ]
    team_name = view_state["values"]["block_team_name"]["input_team_name"]["value"]
    logger.info(
        "%s has requested an org with business_unit=%s and "
        "team_name=%s" % (requesting_user, business_unit, team_name)
    )

    # Save this data for the next action handler
    channel_datastore[channel_id] = {
        "business_unit": business_unit,
        "team_name": team_name,
        "requesting_user": requesting_user,
    }
    if not snyk_user:
        logger.warning(
            "%s(%s) does not have a matching user in Snyk"
            " - prompting them to log in" % (requesting_user, requesting_user_email),
        )
        say(
            channel=channel_id,
            blocks=load_blocks_views(
                "blocks/sso_confirm",
                sso_provider_name=sso_provider_name,
                sso_provider_link=sso_provider_link,
            ),
        )
    else:
        logger.info(
            "%s(%s) found a matching user in snyk - confirming request"
            % (requesting_user, requesting_user_email),
        )
        confirm_org(None, say, channel_id)


@app.action("action-sso-confirmed")
def confirm_org(ack, say, channel_id):
    """
    Handles when the user clicks confirm button when asked to confirm new org details
    :param ack:  slack ack
    :param say: slack say
    :param channel_id: the channel ID we've open with the user (private thread)
    """
    if ack:
        ack()
    business_unit = channel_datastore[channel_id]["business_unit"]
    team_name = channel_datastore[channel_id]["team_name"]
    logger.info(
        "Request for %s-%s has been confirmed - attempting to create organisation"
        % (business_unit, team_name),
    )
    say(
        channel=channel_id,
        blocks=load_blocks_views(
            "blocks/create_confirm", business_unit=business_unit, team_name=team_name
        ),
    )


@app.action("action-cancelled")
def handle_cancelled(ack, body, say):
    ack()
    channel_id = body["channel"]["id"]
    say(
        text=get_chat_message(
            "org_creation",
            "message_cancelled",
        ),
        channel=channel_id,
    )


@app.action("action-confirmed")
def handle_sso_confirm(ack, body, say):
    """
    Handles when the user clicks the "I've signed in via SSO" button
    :param ack:  slack ack
    :param say: slack say
    :param body: slack body
    """
    ack()
    channel_id = body["channel"]["id"]
    data = channel_datastore[channel_id]
    business_unit = data["business_unit"]
    team_name = data["team_name"]
    requesting_user = data["requesting_user"]
    requesting_user_email = app.client.users_info(user=requesting_user["id"])["user"][
        "profile"
    ]["email"]
    new_org_name = f"{business_unit}-{team_name}"

    # Ensure org name matches defined pattern
    if not business_unit_pattern.match(business_unit) or not team_name_pattern.match(
        team_name
    ):
        logger.warning(
            "Request for %s did not match required patterns (business_unit=%s team_name=%s)"
            % (new_org_name, business_unit_pattern, team_name_pattern),
        )
        say(
            text=get_chat_message("org_creation", "error_org_policy"),
            channel=channel_id,
        )
        return

    # Make sure there's not a duplicate org name
    if not settings.config("allow_duplicate_org_names") and api.org_name_exists(
        new_org_name
    ):
        logger.warning(
            "%s already exists in Snyk and allow_duplicate_org_names is set to False"
            " - rejecting" % new_org_name
        )
        say(
            text=get_chat_message(
                "org_creation",
                "error_org_already_exists_message",
                new_org_name=new_org_name,
            ),
            channel=channel_id,
        )
        org = api.get_org_from_name(new_org_name)
        admins = Settings.get_org_admins(org)
        email_admins = [x.email for x in admins]
        admins_str = ", ".join(email_admins)
        if len(email_admins) > 0:
            logger.info(
                "Found existing admins for %s [%s]" % (new_org_name, admins_str)
            )
            say(
                text=get_chat_message(
                    "org_creation",
                    "message_tell_admins_existing_org",
                    admins_str=admins_str,
                ),
                channel=channel_id,
            )
        else:
            logger.warning(
                "Requested organisation %s already exists and DOES NOT have any admins"
                " associated - cannot proceed" % new_org_name
            )
            say(
                text=get_chat_message("org_creation", "error_org_no_admins"),
                channel=channel_id,
            )
        return

    # Ensure the requesting user actually exists
    snyk_user = api.get_user(requesting_user_email)
    if not snyk_user:
        logger.warning(
            "%s still does not exist in Snyk despite SSO log in confirmation"
            % requesting_user_email
        )
        say(
            text=get_chat_message(
                "org_creation",
                "error_snyk_user_not_found",
                sso_provider_name=sso_provider_name,
            ),
            channel=channel_id,
        )
        return

    # Now we can go ahead and create the org
    result = api.create_organisation(new_org_name)

    # Add the user to the org
    api.add_user_to_org(result["id"], snyk_user["id"])

    # Let the user know we've created their org
    if result:
        org_name = result["name"]
        org_id = result["id"]
        result_url = result["url"]
        logger.info("Org creation successful [name=%s, id=%s]" % (org_name, org_id))
        say(
            channel=channel_id,
            blocks=load_blocks_views(
                "blocks/org_created",
                org_name=org_name,
                org_id=org_id,
                result_url=result_url,
            ),
        )
    else:
        logger.warning(
            "An error occurred while trying to create the Snyk organisation - informing user"
        )
        say(
            text=get_chat_message("org_creation", "error_org_create"),
            channel=channel_id,
        )
    del channel_datastore[channel_id]


if __name__ == "__main__":
    # Load all of our jinja templates for chat messages
    logger.info("Loading chat template messages...")
    chat_messages = load_chat_message_templates()
    logger.info("...done")

    # Start up our bot
    logger.info("Starting Snyk org Slack bot...")
    SocketModeHandler(app, os.getenv("slack_app_token_env_var_name")).start()
