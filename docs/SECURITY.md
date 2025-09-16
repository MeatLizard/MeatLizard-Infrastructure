# Security

This document outlines the security measures implemented in the MeatLizard AI Chat System.

## TLS Encryption

All communication between the user and the web server is encrypted using TLS.

## Secrets Management

All secrets, such as API tokens and database credentials, are stored in environment variables or a secret manager.

## AES-256-GCM Encryption

All bot payloads are encrypted using AES-256-GCM to ensure the privacy of user data.

## Strict Discord Permissions

The server-bot and client-bot are configured with strict Discord permissions to prevent unauthorized access.

## Moderation Filters

All user input is passed through a moderation filter to prevent abuse.

## Opt-in Transcripts

Transcripts of chat sessions are only saved if the user explicitly opts in.