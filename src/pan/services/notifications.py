import discord
import structlog

logger = structlog.get_logger()

_bot_instance: discord.Client | None = None


def set_bot(bot: discord.Client) -> None:
    global _bot_instance
    _bot_instance = bot


async def send_notification(message: str) -> bool:
    from pan.config.settings import get_settings

    if _bot_instance is None:
        logger.warning("notification_skipped", reason="bot_not_set")
        return False

    channel_id = get_settings().discord.notification_channel_id
    if channel_id is None:
        logger.warning("notification_skipped", reason="no_notification_channel")
        return False

    channel = _bot_instance.get_channel(channel_id)
    if channel is None:
        logger.warning("notification_skipped", reason="channel_not_found", channel_id=channel_id)
        return False

    if not isinstance(channel, discord.abc.Messageable):
        logger.warning("notification_skipped", reason="channel_not_messageable")
        return False

    try:
        await channel.send(message)
        return True
    except Exception:
        logger.exception("notification_send_failed", channel_id=channel_id)
        return False


async def notify_payment_received(
    tenant_name: str, amount: float, sender_name: str, match_status: str
) -> None:
    if match_status == "matched":
        msg = f"💰 **Rent Payment Received**\n{sender_name} → {tenant_name}: **${amount:,.2f}**"
    elif match_status == "partial":
        msg = (
            f"⚠️ **Possible Rent Payment**\n{sender_name} sent **${amount:,.2f}** — "
            f"partial match to {tenant_name}. Please verify in the admin panel."
        )
    else:
        msg = (
            f"❓ **Unmatched Zelle Payment**\n{sender_name} sent **${amount:,.2f}** — "
            f"could not match to any tenant. Review in admin panel."
        )
    await send_notification(msg)


async def notify_reconciliation_summary(
    month: str, total_expected: float, total_received: float, unpaid_tenants: list[str]
) -> None:
    shortfall = max(0, total_expected - total_received)
    lines = [
        f"📊 **Monthly Rent Summary — {month}**",
        f"Expected: **${total_expected:,.2f}** | Received: **${total_received:,.2f}**",
    ]
    if shortfall > 0:
        lines.append(f"⚠️ Shortfall: **${shortfall:,.2f}**")
    else:
        lines.append("✅ All rent collected!")

    if unpaid_tenants:
        lines.append(f"\nUnpaid: {', '.join(unpaid_tenants)}")

    await send_notification("\n".join(lines))
