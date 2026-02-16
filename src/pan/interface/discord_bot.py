from __future__ import annotations

import asyncio
import traceback
from typing import Any

import discord
import structlog
from discord import app_commands
from discord.ext import commands
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from pan.config.settings import DiscordSettings
from pan.interface.discord_views import ApprovalView
from pan.orchestration.router import resume_after_approval, route_message

logger = structlog.get_logger()

MAX_MESSAGE_LENGTH = 2000


class PanBot(commands.Bot):
    def __init__(
        self,
        settings: DiscordSettings,
        graph: CompiledStateGraph,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self.settings = settings
        self.graph = graph
        self._pending_approvals: dict[str, ApprovalView] = {}
        self._managed_threads: set[int] = set()

    async def setup_hook(self) -> None:
        await self.add_cog(AgentCog(self))

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("commands_synced", guild_id=self.settings.guild_id)
        else:
            await self.tree.sync()
            logger.info("commands_synced_globally")

    async def on_ready(self) -> None:
        logger.info("discord_bot_ready", user=str(self.user))

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user or message.author.bot:
            return

        if isinstance(message.channel, discord.Thread):
            if message.channel.id in self._managed_threads:
                await self._handle_thread_followup(message)
                return

        if self.user and self.user.mentioned_in(message) and not message.mention_everyone:
            await self._handle_mention(message)
            return

        await self.process_commands(message)

    async def _handle_thread_followup(self, message: discord.Message) -> None:
        thread = message.channel
        thread_id = str(thread.id)
        user_id = str(message.author.id)
        user_role = self._get_user_role(message.author.id)

        logger.info(
            "thread_followup",
            thread_id=thread_id,
            user_id=user_id,
            message_preview=message.content[:100],
        )

        async with thread.typing():
            try:
                async for event in route_message(
                    self.graph,
                    message.content,
                    user_id=user_id,
                    user_role=user_role,
                    thread_id=thread_id,
                ):
                    for _node_name, node_output in event.items():
                        if not isinstance(node_output, dict):
                            continue
                        for msg in node_output.get("messages", []):
                            if isinstance(msg, AIMessage) and msg.content:
                                await _send_long_message(thread, str(msg.content))
            except Exception as exc:
                tb = "".join(traceback.format_exception(exc))
                logger.exception(
                    "thread_followup_error",
                    thread_id=thread_id,
                    error_type=type(exc).__name__,
                )
                await _send_long_message(thread, f"```\n{tb[-1800:]}\n```")

    async def _handle_mention(self, message: discord.Message) -> None:
        content = message.content
        if self.user:
            content = content.replace(f"<@{self.user.id}>", "").strip()
            content = content.replace(f"<@!{self.user.id}>", "").strip()

        if not content:
            await message.reply("Hey! Ask me something or use `/ask` to talk to a specific agent.")
            return

        user_id = str(message.author.id)
        user_role = self._get_user_role(message.author.id)

        initial_reply = await message.reply("Working on it...")
        thread = await initial_reply.create_thread(
            name=f"Pan: {content[:80]}",
            auto_archive_duration=1440,
        )
        thread_id = str(thread.id)
        self._managed_threads.add(thread.id)

        logger.info(
            "mention_received",
            thread_id=thread_id,
            user_id=user_id,
            message_preview=content[:100],
        )

        try:
            async for event in route_message(
                self.graph,
                content,
                user_id=user_id,
                user_role=user_role,
                thread_id=thread_id,
            ):
                for _node_name, node_output in event.items():
                    if not isinstance(node_output, dict):
                        continue
                    for msg in node_output.get("messages", []):
                        if isinstance(msg, AIMessage) and msg.content:
                            await _send_long_message(thread, str(msg.content))
        except Exception as exc:
            tb = "".join(traceback.format_exception(exc))
            logger.exception(
                "mention_error",
                thread_id=thread_id,
                error_type=type(exc).__name__,
            )
            await _send_long_message(thread, f"```\n{tb[-1800:]}\n```")

    def _is_admin(self, user_id: int) -> bool:
        return user_id in self.settings.admin_user_ids

    def _get_user_role(self, user_id: int) -> str:
        if self._is_admin(user_id):
            return "owner"
        return "tenant"


class AgentCog(commands.Cog, name="Pan Agents"):
    def __init__(self, bot: PanBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ask",
        description="Ask a Pan agent a question or give it a task",
    )
    @app_commands.describe(
        domain="Which agent to ask",
        question="Your question or task description",
    )
    @app_commands.choices(
        domain=[
            app_commands.Choice(name="Tech Chair", value="tech_chair"),
            app_commands.Choice(name="House Manager", value="house_manager"),
            app_commands.Choice(name="Auto (let Pan decide)", value="auto"),
        ]
    )
    async def ask_command(
        self,
        interaction: discord.Interaction,
        domain: str,
        question: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        target_domain = domain if domain != "auto" else None
        user_id = str(interaction.user.id)
        user_role = self.bot._get_user_role(interaction.user.id)

        domain_label = domain.replace("_", " ").title() if domain != "auto" else "Pan"
        await interaction.followup.send(f"**{domain_label}** is working on: {question[:200]}")

        channel = interaction.channel
        initial_msg = await channel.send(f"🧵 **{domain_label}** — {question[:100]}")
        thread = await initial_msg.create_thread(
            name=f"{domain_label}: {question[:80]}",
            auto_archive_duration=1440,
        )
        thread_id = str(thread.id)
        self.bot._managed_threads.add(thread.id)

        try:
            async for event in route_message(
                self.bot.graph,
                question,
                user_id=user_id,
                user_role=user_role,
                thread_id=thread_id,
                target_domain=target_domain,
            ):
                await self._handle_graph_event(event, thread, thread_id)

        except Exception as exc:
            tb = "".join(traceback.format_exception(exc))
            logger.exception(
                "ask_command_error",
                thread_id=thread_id,
                error_type=type(exc).__name__,
                error_detail=str(exc),
            )
            await _send_long_message(thread, f"```\n{tb[-1800:]}\n```")

    @app_commands.command(
        name="status",
        description="Check Pan system status",
    )
    async def status_command(self, interaction: discord.Interaction) -> None:
        from pan.agents.registry import list_domains

        domains = list_domains()
        domain_list = "\n".join(f"  - {d.replace('_', ' ').title()}" for d in domains)

        await interaction.response.send_message(
            f"**Pan Status**\n"
            f"Active Agents:\n{domain_list}\n"
            f"Bot Latency: {self.bot.latency * 1000:.0f}ms",
            ephemeral=True,
        )

    async def _handle_graph_event(
        self,
        event: dict[str, Any],
        thread: discord.Thread,
        thread_id: str,
    ) -> None:
        for _node_name, node_output in event.items():
            if not isinstance(node_output, dict):
                continue

            if "__interrupt__" in node_output:
                interrupts = node_output["__interrupt__"]
                for interrupt_data in interrupts:
                    await self._handle_interrupt(interrupt_data, thread, thread_id)
                return

            messages = node_output.get("messages", [])
            for msg in messages:
                if isinstance(msg, AIMessage) and msg.content:
                    await _send_long_message(thread, str(msg.content))

    async def _handle_interrupt(
        self,
        interrupt_data: Any,
        thread: discord.Thread,
        thread_id: str,
    ) -> None:
        if hasattr(interrupt_data, "value"):
            payload = interrupt_data.value
        else:
            payload = str(interrupt_data)

        if isinstance(payload, dict):
            description = payload.get("description", payload.get("question", str(payload)))
        else:
            description = str(payload)

        view = ApprovalView(
            approval_id=thread_id,
            bot=self.bot,
            thread_id=thread_id,
        )
        self.bot._pending_approvals[thread_id] = view

        await thread.send(
            f"**Approval Required**\n{description}",
            view=view,
        )

        try:
            approved = await asyncio.wait_for(view.future, timeout=300.0)
        except TimeoutError:
            approved = False
            await thread.send("Approval timed out. Action rejected.")
        finally:
            self.bot._pending_approvals.pop(thread_id, None)

        async for event in resume_after_approval(
            self.bot.graph,
            thread_id=thread_id,
            approved=approved,
        ):
            await self._handle_graph_event(event, thread, thread_id)


async def _send_long_message(channel: discord.abc.Messageable, text: str) -> None:
    if len(text) <= MAX_MESSAGE_LENGTH:
        await channel.send(text)
        return

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_MESSAGE_LENGTH:
            if current:
                chunks.append(current)
            current = line[:MAX_MESSAGE_LENGTH]
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)

    for chunk in chunks:
        await channel.send(chunk)
        await asyncio.sleep(0.1)
