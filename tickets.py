import discord

from discord.ext import commands
from discord import app_commands

from database import(
    get_guild_settings,
    get_ticket_settings,
    save_ticket_settings
)

def register_ticket_commands(bot: commands.Bot):

    @bot.tree.command(
        name="ticketsetup",
        description="Configure ticket settings"
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticketsetup(
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
        log_channel: discord.TextChannel | None = None
    ):
        guild_settings = await get_guild_settings(interaction.guild.id)

        if guild_settings is None:
            await interaction.response.send_message(
                "Beacon must be set up with /setup before configuring tickets.",
                ephemeral=True
            )
            return
        
        await save_ticket_settings(
            interaction.guild.id,
            category.id,
            log_channel.id if log_channel else None
        )

        await interaction.response.send_message(
            "Ticket settings saved.",
            ephemeral=True
        )