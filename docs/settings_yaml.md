# Configuring bot settings
Please see `settings.yaml.example` for an example of settings. 

## Settings
| **Setting name**             | **Description**                                                                                                        | **Required?** |
|------------------------------|------------------------------------------------------------------------------------------------------------------------|---------------|
| slack_bot_token_env_var_name | The Slack bot token                                                                                                    | Yes           |
| slack_app_token_env_var_name | The Slack app token                                                                                                    | Yes           |
| snyk_token_env_var_name      | The environment variable name that we'll pull the snyk token from                                                      | Yes           |
| snyk_group_id                | The ID of the Snyk group where we'll create orgs                                                                       | Yes           |
| allow_duplicate_org_names    | If set to false this will not allow duplicate org names to be served by the bot                                        | Yes           |
| business_unit_regex_pattern  | The regex pattern that the business unit must follow                                                                   | Yes           |
| team_name_regex_pattern      | The regex pattern that the team name must follow                                                                       | Yes           |
| command_create_org           | The slash command to create an org (the same as the one you will have generated in the Slack app step - without the /) | Yes           |
| sso_sign_in_link             | The sign in link to your SSO provider - will prompt the user to log in via this link                                   | Yes           |
| sso_provider_name            | The name of your SSO provider                                                                                          | Yes           |