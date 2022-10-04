import os
import re

from api import SnykApiFacade
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


@app.command(f"/{command_create_org}")
def create_org_modal(ack, body, client, say):
    ack()
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "create_org_callback",
            "title": {"type": "plain_text", "text": "Snyk Org Creation Tool"},
            "submit": {"type": "plain_text", "text": "Create my organisation"},
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Let's get started.* To create your Snyk org, I'll first need some information from"
                        " you.",
                    },
                },
                {"type": "divider"},
                {
                    "type": "input",
                    "block_id": "block_business_unit",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input_business_unit",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "What's the name of your business unit?",
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "block_team_name",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "input_team_name",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "And what's the name of your team?",
                        "emoji": True,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": "*Note:* The final org name will be your business unit and team name combined",
                        }
                    ],
                },
                {
                    "type": "input",
                    "block_id": "block_agreements",
                    "element": {
                        "type": "checkboxes",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "I understand I will initially be responsible for adding team members and "
                                    "managing their permissions",
                                    "emoji": True,
                                },
                                "value": "ack_responsible",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "I have permission to create a Snyk organisation for my team and business"
                                    " unit",
                                    "emoji": True,
                                },
                                "value": "ack_permission",
                            },
                        ],
                        "action_id": "checkboxes-action",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Agreements",
                        "emoji": True,
                    },
                },
            ],
        },
    )


@app.view("create_org_callback")
def handle_view_events(ack, body, client, say):
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
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Great, I've got your request!*",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Before your request is processed you *must* first log in to Snyk via {sso_provider_name}. This is to ensure that when we create your org we can assign you admin rights. <{sso_provider_link}|Open {sso_provider_name}>",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": f":white_check_mark: I've signed in via {sso_provider_name}",
                                "emoji": True,
                            },
                            "value": "sso_confirmed",
                            "action_id": "action-sso-confirmed",
                        }
                    ],
                },
            ],
        )
    else:
        confirm_org(None, say, channel_id)


@app.action("action-sso-confirmed")
def confirm_org(ack, say, channel_id):
    if ack:
        ack()
    say(
        channel=channel_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Great! - We're set* I'll create an org named *{channel_datastore[channel_id]['business_unit']}-{channel_datastore[channel_id]['team_name']}* - does that look right?",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":white_check_mark: Looks good!",
                            "emoji": True,
                        },
                        "style": "primary",
                        "value": "confirmed",
                        "action_id": "action-confirmed",
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":no_entry: Something looks wrong",
                            "emoji": True,
                        },
                        "style": "danger",
                        "value": "cancelled",
                        "action_id": "action-cancelled",
                    },
                ],
            },
        ],
    )


@app.action("action-confirmed")
def handle_sso_confirm(ack, body, client, say):
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
        say(
            channel=channel_id,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":white_check_mark: *Looks good!* I have created your Snyk organisation and added you as an"
                        " administrator user, here are the details:",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"The name of your organisation is *{result['name']}* and it's ID is *{result['id']}*",
                    },
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Link to your organisation"},
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Click To Open",
                            "emoji": True,
                        },
                        "value": "click_me_123",
                        "url": result["url"],
                        "action_id": "button-action",
                    },
                },
            ],
        )
    else:
        say(
            text=f"An error occurred and I wasn't able to create your organisation",
            channel=channel_id,
        )
    del channel_datastore[channel_id]


@app.action("button-action")
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)


if __name__ == "__main__":
    SocketModeHandler(
        app, os.environ[settings.config("slack_app_token_env_var_name")]
    ).start()
