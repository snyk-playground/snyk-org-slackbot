# Customization
The views and modal views in this app are created using Slacks "block kit". You can update the JSON
structure of these views to customize the bot to your liking. An easy way to get started with block
kit is by using the [block kit builder](https://app.slack.com/block-kit-builder) provided by slack.

**Things to watch out for:**
* The "action ids" must remain the same. If you change these, you will also need to update the 
Python source code accordingly. 
* The views and chat messages are all templated using 
[Jinja2](https://jinja.palletsprojects.com/en/3.1.x/). If you wish to pass new variables through to
Jinja, again, you must update the underlying source code in order to do this.
* After updating a view, you must restart your application for the changes to come in to effect

## Changing the modal view
The modal view is the main view that pops up when a user requests to create an organisation. This
view is built using Block Kit and can be found in `templates/views/create_org_modal.json`.

## Changing interactive chat messages
Some chat messages the bot sends are interactive (they have buttons amongst other inputs). These
chat messages are located in `templates/blocks`, each file is described below:

| **File path**                       | **What it does**                                                                                                                                                   |
|-------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| template/blocks/create_confirm.json | Once a request has passed all of the checks, the bot will send one final message asking the user to click a button to confirm they've provided the correct details |
| template/blocks/org_created         | When an org has been created, this will show the user details of that org, as well as a button to open it in Snyk                                                  |
| template/blocks/sso_confirm         | If the user wasn't found in SSO, then we prompt them to log in and click a button once this is done                                                                |

## Changing standard chat messages
Standard chat messages (those not built with Block Kit) are easier to change. They are all defined
in a single YAML file and also templated with Jinja2. The chat messages for org creation, for
example can be found at `templates/messages/org_creation.yaml`. 