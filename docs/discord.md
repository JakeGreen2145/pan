# Discord Integration

Pan uses a Discord bot as its primary user interface. Users interact with agents through slash commands, and agents can request human approval via interactive buttons.

## Creating the Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application**, name it (e.g. "Pan")
3. Go to **Bot** in the sidebar
4. Click **Reset Token** and copy it — this is your `PAN_DISCORD__TOKEN`
5. Under **Privileged Gateway Intents**, enable **Message Content Intent**

### Inviting the Bot

Go to **OAuth2 → URL Generator** and select:

- **Scopes**: `bot`, `applications.commands`
- **Bot Permissions**: `Send Messages`, `Create Public Threads`, `Send Messages in Threads`, `Embed Links`, `Read Message History`

Copy the generated URL and open it to invite the bot to your server.

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `PAN_DISCORD__TOKEN` | Yes | Bot token from the Developer Portal |
| `PAN_DISCORD__GUILD_ID` | No | Server ID for instant slash command sync (recommended for dev). Omit for global sync. |
| `PAN_DISCORD__ADMIN_USER_IDS` | No | JSON list of Discord user IDs that can approve/reject agent actions. e.g. `[123456789, 987654321]` |
| `PAN_DISCORD__NOTIFICATION_CHANNEL_ID` | No | Channel ID for scheduled task notifications |

### Finding IDs

Enable **Developer Mode** in Discord (Settings → Advanced → Developer Mode), then right-click any server, channel, or user to copy its ID.

## Slash Commands

| Command | Description |
|---------|-------------|
| `/ask <domain> <question>` | Route a question to a specific agent or let the supervisor choose ("Auto") |
| `/status` | Show active agents and bot latency (ephemeral — only you see it) |

### How `/ask` works

1. User runs `/ask` and picks a domain (Tech Chair, House Manager, or Auto)
2. Bot defers the response and posts an initial message
3. A thread is created off that message for the full conversation
4. The message is routed through the LangGraph supervisor (or directly to the chosen agent)
5. Agent responses stream into the thread as they're produced
6. If an agent triggers an approval interrupt, the bot presents Approve/Reject buttons

## Approval Flow

Some agent actions require human approval before executing. When this happens:

1. The agent raises a LangGraph `interrupt` with a description of the pending action
2. The bot posts an **Approval Required** message in the thread with two buttons
3. Only users in `PAN_DISCORD__ADMIN_USER_IDS` can click Approve or Reject
4. The approval times out after **5 minutes** — timeout counts as rejection
5. The graph resumes with the decision, and the agent continues (or aborts)

## User Roles

The bot assigns roles based on `admin_user_ids`:

| Discord User | Pan Role | Permissions |
|-------------|----------|-------------|
| In `admin_user_ids` | `owner` | Full access, can approve actions |
| Everyone else | `tenant` | Can ask questions, cannot approve |

## Code Reference

| File | Purpose |
|------|---------|
| `src/pan/interface/discord_bot.py` | `PanBot` class, slash commands, event streaming |
| `src/pan/interface/discord_views.py` | `ApprovalView` — approve/reject button UI |
| `src/pan/config/settings.py` | `DiscordSettings` model |
