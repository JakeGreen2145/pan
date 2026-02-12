from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from pan.interface.discord_bot import PanBot


class ApprovalView(discord.ui.View):
    def __init__(
        self,
        *,
        approval_id: str,
        bot: PanBot,
        thread_id: str,
        timeout: float = 300.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.approval_id = approval_id
        self.bot = bot
        self.thread_id = thread_id
        self.decision: bool | None = None
        self._future: asyncio.Future[bool] = asyncio.get_event_loop().create_future()

    @property
    def future(self) -> asyncio.Future[bool]:
        return self._future

    def _disable_all(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green)
    async def approve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id not in self.bot.settings.admin_user_ids:
            await interaction.response.send_message(
                "You don't have permission to approve actions.", ephemeral=True
            )
            return

        self.decision = True
        self._disable_all()
        await interaction.response.edit_message(
            content=f"Approved by {interaction.user.mention}", view=self
        )
        if not self._future.done():
            self._future.set_result(True)
        self.stop()

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.user.id not in self.bot.settings.admin_user_ids:
            await interaction.response.send_message(
                "You don't have permission to reject actions.", ephemeral=True
            )
            return

        self.decision = False
        self._disable_all()
        await interaction.response.edit_message(
            content=f"Rejected by {interaction.user.mention}", view=self
        )
        if not self._future.done():
            self._future.set_result(False)
        self.stop()

    async def on_timeout(self) -> None:
        self._disable_all()
        if not self._future.done():
            self._future.set_result(False)
