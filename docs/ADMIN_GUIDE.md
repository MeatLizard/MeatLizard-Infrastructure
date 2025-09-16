# Admin Guide

This guide provides instructions for administering the MeatLizard AI Chat System.

## Slash Commands

The server-bot provides the following slash commands for administering the system:

-   `/ai start`: Start a new AI chat session.
-   `/ai set-system <prompt>`: Set the system prompt for the current session.
-   `/ai set-temp <temperature>`: Set the temperature for the current session.
-   `/ai end`: End the current AI chat session.
-   `/ai gdpr-anonymize`: Anonymize your user data.

## Admin-Only Commands

The server-bot also provides the following admin-only slash commands:

-   `/admin enable-requests`: Enable or disable requests from the web UI.
-   `/admin transfer-session <session-id> <user-id>`: Transfer a session to another user.
-   `/admin metrics`: View the latest metrics from the client-bot.
-   `/admin backup`: Create a backup of the database and transcripts.
