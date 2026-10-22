
import discord
import traceback

from discord.ext import commands
from discord import app_commands
from suggestions import SetupView, register_suggestion_commands
from config import TOKEN
from database import (
    init_database, 
    get_guild_settings, 
    save_guild_settings, 
    update_guild_settings
)

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!", 
    intents=intents
)

register_suggestion_commands(bot)
##CLASSES

class SetupModal(discord.ui.Modal, title="Beacon Setup"):
    panel_channel = discord.ui.Label(
        text="Panel Channel",
        description="Where Beacon's suggestion button will be posted.",
        component=discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            required=True
        )
    )

    suggestion_channel = discord.ui.Label(
        text="Suggestion Channel",
        description="Where new suggestions will be posted.",
        component=discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            required=True
        )
    )

    archive_channel = discord.ui.Label(
        text="Archive Channel",
        description="Where finalized suggestions will be stored.",
        component=discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            required=True
        )
    )

    staff_role = discord.ui.Label(
        text="Staff Role",
        description="The role that will have access to manage suggestions.",
        component=discord.ui.RoleSelect(
            required=True
        )
    )

    async def on_submit(self, interaction: discord.Interaction):
        selected_panel_channel = self.panel_channel.component.values[0]
        suggestion_channel = self.suggestion_channel.component.values[0]
        archive_channel = self.archive_channel.component.values[0]
        staff_role = self.staff_role.component.values[0]

        panel_channel = interaction.guild.get_channel(selected_panel_channel.id)

        if panel_channel is None:
            await interaction.response.send_message(
                "Couldnt find the selected panel channel.",
                ephemeral=True
            )
            return

        await panel_channel.send(
                "Click the button below to submit a suggestion!",
                view=SetupView()
            )

        await save_guild_settings(
            guild_id=interaction.guild.id,
            suggestion_channel_id=suggestion_channel.id,
            archive_channel_id=archive_channel.id,
            staff_role_id=staff_role.id
        )

        await interaction.response.send_message(
            "Beacon has been set up successfully!",
            ephemeral=True
        )

class PanelView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id

    @discord.ui.button(
        label="Show Server ID",
        style=discord.ButtonStyle.secondary
    )
    async def show_guild_id(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_message(
            f"Server ID: {self.guild_id}",
            ephemeral=True 
        )

class SettingsChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setting_name: str, placeholder: str):
        super().__init__(
            channel_types=[discord.ChannelType.text],
            placeholder=placeholder,
            min_values=1,
            max_values=1
        )

        self.setting_name = setting_name

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]

        await update_guild_settings(
            guild_id=interaction.guild.id,
            **{self.setting_name: selected_channel.id}
        )

        settings = await get_guild_settings(interaction.guild.id)

        embed = discord.Embed(
            title="Channel Settings",
            description="Changes are saved automatically."
        )

        embed.add_field(
            name="Suggestion Channel",
            value=f"<#{settings['suggestion_channel_id']}>",
            inline=False
        )

        embed.add_field(
            name="Archive Channel",
            value=f"<#{settings['archive_channel_id']}>",
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=ChannelSettingsView()
        )

class ChannelSettingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

        self.add_item(
            SettingsChannelSelect(
                "suggestion_channel_id",
                "Change Suggestion Channel"
            )
        )

        self.add_item(
            SettingsChannelSelect(
                "archive_channel_id",
                "Change Archive Channel"
            )
        )



##Persistent view setup to keep the button active even after bot restarts
async def setup_hook():
    await init_database()
    bot.add_view(SetupView())

    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands globally.")

bot.setup_hook=setup_hook

##On ready event and command syncing
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")

##Error handling for application commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need Manage Server permission to use this command.",
            ephemeral=True
        )
    elif isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You don't have the required Staff Role to use this command.",
            ephemeral=True
        )
    else:
        traceback.print_exception(
            type(error), 
            error, 
            error.__traceback__
        )

        if interaction.response.is_done():
            await interaction.followup.send(
                "An unexpected error occurred while processing the command.",
                ephemeral=True
            )
        else:
                await interaction.response.send_message(
                    "An error occurred while processing the command.",
                    ephemeral=True
                )


##COMMANDS

##Ping command to check if the bot is online
@bot.tree.command(name="ping", description="Check to see if the bot is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

##Setup command to initialize Beacon for a server, only usable by users with manage_guild permissions
@bot.tree.command(name="setup", description="Set up Beacon for a server for the first time")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def setup(interaction: discord.Interaction):
    existing_settings = await get_guild_settings(interaction.guild.id)

    if existing_settings is not None:
        await interaction.response.send_message(
            "Beacon has already been set up for this server. "
            "Use '/settings' to change settings.",
            ephemeral=True
        )
        return
    
    await interaction.response.send_modal(SetupModal())

##Command that allows admins to see current Beacon settings
@bot.tree.command(name="panel", description="View current Beacon configuration")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def panel(interaction: discord.Interaction):
    guild_settings = await get_guild_settings(interaction.guild.id)

    if not guild_settings:
        await interaction.response.send_message(
            "No Beacon settings found for this server.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Current Beacon Settings"
    )

    embed.add_field(
        name="Suggestion Channel",
        value=f"<#{guild_settings['suggestion_channel_id']}>",
        inline=False
    )

    embed.add_field(
        name="Archive Channel",
        value=f"<#{guild_settings['archive_channel_id']}>",
        inline=False
    )

    if guild_settings['staff_role_id']:
        embed.add_field(
            name="Staff Role",
            value=f"<@&{guild_settings['staff_role_id']}>",
            inline=False
        )

    embed.add_field(
        name="Anonymous Suggestions",
        value="Enabled" if guild_settings['anonymous_enabled'] else "Disabled",
        inline=False
    )

    embed.add_field(
        name="Voting System",
        value="Enabled" if guild_settings['voting_enabled'] else "Disabled",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        view=PanelView(interaction.guild.id), 
        ephemeral=True
        )

##Command to view and change Beacon settings, only usable by users with manage_guild permissions
@bot.tree.command(name="settings", description="Configure Beacon settings")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def settings_command(interaction: discord.Interaction):
    settings = await get_guild_settings(interaction.guild.id)

    if settings is None:
        await interaction.response.send_message(
            "Beacon has not been setup for this server yet.",
            ephemeral=True
        )
        return

    embed = discord.Embed(title="Channel Settings", description="Changes are saved automatically")

    # Add fields to the embed based on the settings
    embed.add_field(
        name="Suggestion Channel",
        value=f"<#{settings['suggestion_channel_id']}>",
        inline=False
    )

    embed.add_field(
        name="Archive Channel",
        value=f"<#{settings['archive_channel_id']}>",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed, 
        view=ChannelSettingsView(),
        ephemeral=True
    )

bot.run(TOKEN)
