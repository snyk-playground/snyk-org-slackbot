import json
import os
import re

from api import SnykApiFacade
from jinja2 import Environment, FileSystemLoader
from settings import Settings
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

SETTINGS_FILE = os.environ["SETTINGS_FILE_PATH"]

# Load settings from a file
settings = Settings.from_file(SETTINGS_FILE)
# In memory persistence
channel_datastore = {}
# Set up our API facade
api = SnykApiFacade(settings)
# Set up our Slack app
app = App(token=os.environ[settings.config("slack_bot_token_env_var_name")])
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


def load_blocks_views(view_name, **kwargs):
    """
    Will load a view, template it with the args given and return a python object
    :param view_name: the name of the view (file name without .json)
    :param kwargs: kwargs
    :return: python object representation of the view
    """
    template = environment.get_template(f"{view_name}.json")
    str_output = template.render(kwargs)
    print(str_output)
    return json.loads(str_output)


@app.command(f"/{command_create_org}")
def create_org_modal(ack, body, client):
    """
    Shows the initial modal for org creation (user input screen)
    :param ack: slack ack
    :param body: slack body
    :param client: slack client
    """
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

    # Let's open a DM channel with the requesting user
    conversation = client.conversations_open(users=requesting_user["id"])
    channel_id = conversation["channel"]["id"]

    # Extract the input from the modal output
    business_unit = view_state["values"]["block_business_unit"]["input_business_unit"][
        "value"
    ]
    team_name = view_state["values"]["block_team_name"]["input_team_name"]["value"]

    # Save this data for the next action handler
    channel_datastore[channel_id] = {
        "business_unit": business_unit,
        "team_name": team_name,
        "requesting_user": requesting_user,
    }
    if not snyk_user:
        say(
            channel=channel_id,
            blocks=load_blocks_views(
                "blocks/sso_confirm",
                sso_provider_name=sso_provider_name,
                sso_provider_link=sso_provider_link,
            ),
        )
    else:
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
    say(
        channel=channel_id,
        blocks=load_blocks_views(
            "blocks/create_confirm", business_unit=business_unit, team_name=team_name
        ),
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
        say(
            text=f"The name of the organisation you gave didn't match your organisational policies, please try again.",
            channel=channel_id,
        )
        return

    # Make sure there's not a duplicate org name
    if not settings.config("allow_duplicate_org_names") and api.org_name_exists(
        new_org_name
    ):
        say(
            text=f":warning: I'm really sorry, your requested org '{new_org_name}' already exists. Your administrator does not "
            f"allow duplicate org names. Please use the existing organisation :warning:",
            channel=channel_id,
        )
        org = api.get_org_from_name(new_org_name)
        admins = api.get_org_admins(org)
        email_admins = [x.email for x in admins]
        if len(email_admins) > 0:
            say(
                text=f"If you need access to this organisation, please reach out to one of the existing org admins - {', '.join(email_admins)}",
                channel=channel_id,
            )
        else:
            say(
                text=f":no_entry: It looks like this existing org doesn't have any admins.. Please reach out to your Snyk administrator for further help! :no_entry:",
                channel=channel_id,
            )
        return

    # Ensure the requesting user actually exists
    snyk_user = api.get_user(requesting_user_email)
    if not snyk_user:
        say(
            text=f":warning: I couldn't find your user in Snyk - please try again to log-in through {sso_provider_name} and request your"
            f"organisation again!",
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
        say(
            text=f"An error occurred and I wasn't able to create your organisation",
            channel=channel_id,
        )
    del channel_datastore[channel_id]


if __name__ == "__main__":
    SocketModeHandler(
        app, os.environ[settings.config("slack_app_token_env_var_name")]
    ).start()
