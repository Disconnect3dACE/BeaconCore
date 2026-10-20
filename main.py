import os
import discord
import traceback
from discord import guild
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from database import (
    init_database, 
    get_guild_settings, 
    save_guild_settings, 
    update_guild_settings, 
    create_suggestion_record, 
    update_suggestion_discord_ids,
    get_suggestion_record,
    update_suggestion_status
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!", 
    intents=intents
)

##CLASSES

class SuggestionModal(discord.ui.Modal, title="Submit a Suggestion"):
    suggestion = discord.ui.TextInput(
        label="Suggestion",
        style=discord.TextStyle.paragraph,
        placeholder="Enter your suggestion here...",
        required=True,
        max_length=2000
    )

    anonymous = discord.ui.Label(
        text="Submit Anonymously?",
        description="Check this box if you want to submit your suggestion anonymously.",
        component=discord.ui.Checkbox(
            default=False
        )
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        settings = await get_guild_settings(interaction.guild.id)

        if settings is None:
            await interaction.followup.send(
                "This server has not been configured yet.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(
            settings["suggestion_channel_id"]
        )

        if channel is None:
            await interaction.followup.send(
                "I couldn't find the configured suggestion channel.",
                ephemeral=True
            )
            return   

        

        suggestion_id = await create_suggestion_record(
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            author_id=interaction.user.id,
            anonymous=self.anonymous.component.value
        )

        embed = discord.Embed(
            title="New Suggestion",
            description=self.suggestion.value
        )

        embed.add_field(
            name="Suggestion ID",
            value=f"#{suggestion_id:03d}",
            inline=False
        )

        if self.anonymous.component.value:
            embed.set_footer(
            text="Submitted anonymously"
        )
        else:
            embed.set_footer(
            text=f"Suggested by {interaction.user}"
        )

        suggestion_message = await channel.send(embed=embed)

        await suggestion_message.add_reaction("👍")
        await suggestion_message.add_reaction("👎")

        thread = await suggestion_message.create_thread(
            name="Suggestion Discussion"
            )

        await update_suggestion_discord_ids(
            guild_id=interaction.guild.id,
            suggestion_id=suggestion_id,
            message_id=suggestion_message.id,
            thread_id=thread.id
        )

        await thread.send(
        "Use this thread to discuss the current suggestion."
        )
        

        await interaction.followup.send(
            "Thank you for your suggestion!",
            ephemeral=True
        )

class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(
        label="Submit Suggestion",
        style=discord.ButtonStyle.primary,
        custom_id="helpdesk:submit_suggestion"
    )
    async def suggestion_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(SuggestionModal())

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

##Check if a user has the staff role or manage_guild permission
async def is_beacon_staff(interaction: discord.Interaction):
    settings = await get_guild_settings(interaction.guild.id)

    if settings is None:
        return False

    if interaction.user.guild_permissions.manage_guild:
        return True

    staff_role_id = settings["staff_role_id"]

    return any(
        role.id == staff_role_id 
        for role in interaction.user.roles
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

##Approve command for suggestions, only usable by users with staff permissions
@bot.tree.command(name="approve",description="Approve a suggestion")
@app_commands.guild_only()
@app_commands.check(is_beacon_staff)
async def approve(
    interaction: discord.Interaction,
    suggestion_id: int
):
    await interaction.response.defer(ephemeral=True)
    message, embed = await get_suggestion_message_by_id(
        suggestion_id,
        interaction
    )

    if message is None:
        return

    status_updated = await update_suggestion_status(
        guild_id=interaction.guild.id,
        suggestion_id=suggestion_id,
        status="approved",
        decided_by=interaction.user.id
    )

    if not status_updated:
        await interaction.followup.send(
            "This suggestion has already been decided.",
            ephemeral=True
        )
        return
    
    set_status(embed, "✅ Approved")
    await message.edit(embed=embed)

    await interaction.followup.send(
        "Suggestion approved.",
        ephemeral=True
    )

    await archive_suggestion(
        message,
        embed,
        interaction
    )

    await close_suggestion_thread(
        message,
        f"✅ This suggestion has been approved by {interaction.user.display_name}."
    )

##Deny command for suggestions, only usable by users with staff permissions
@bot.tree.command(name="deny",description="Deny a suggestion")
@app_commands.guild_only()
@app_commands.check(is_beacon_staff)
async def deny(
    interaction: discord.Interaction,
    suggestion_id: int
):
    await interaction.response.defer(ephemeral=True)

    message, embed = await get_suggestion_message_by_id(
        suggestion_id,
        interaction
    )

    if message is None:
        return

    status_updated = await update_suggestion_status(
        guild_id=interaction.guild.id,
        suggestion_id=suggestion_id,
        status="denied",
        decided_by=interaction.user.id
    )
    
    if not status_updated:
        await interaction.followup.send(
            "This suggestion has already been decided.",
            ephemeral=True
        )
        return

    set_status(embed, "❌ Denied")
    await message.edit(embed=embed)

    
    await interaction.followup.send(
        "Suggestion denied.",
        ephemeral=True
    )

    await archive_suggestion(
        message,
        embed,
        interaction
    )

    await close_suggestion_thread(
            message,
            f"❌ This suggestion has been denied by {interaction.user.display_name}."
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

@bot.tree.command(name="deploy", description="Deploy/Redeploy the suggestion button to the panel channel")
@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_guild=True)
async def deploy_panel(
    interaction: discord.Interaction,
    channel: discord.TextChannel
):
    settings = await get_guild_settings(interaction.guild.id)

    if settings is None:
        await interaction.response.send_message(
            "Beacon has not been setup for this server yet. Use /setup first.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    await channel.send(
        "Click the button below to submit a suggestion!",
        view=SetupView()
    )

    await interaction.followup.send(
        f"Suggestion button deployed to {channel.mention}.",
        ephemeral=True
    )


##HELPER FUNCTIONS

##Helper function to set the status of a suggestion embed
def set_status(embed: discord.Embed, status: str):
    for index, field in enumerate(embed.fields):
        if field.name == "Status":
            embed.remove_field(index)
            break

    embed.add_field(
        name="Status",
        value=status,
        inline=False
    )

##Helper function for closing a suggestion thread
async def close_suggestion_thread(
    message: discord.Message, 
    closing_message: str
):
    thread = message.thread

    if thread is None:
        return

    await thread.send(closing_message)

    await thread.edit(
        archived=True, 
        locked=True
    )

##Helper function for archiving suggestions
async def archive_suggestion(
        message: discord.Message,
        embed: discord.Embed,
        interaction: discord.Interaction
    ):

        settings = await get_guild_settings(interaction.guild.id)

        if settings is None:
            return
        
        archive_channel = interaction.guild.get_channel(
            settings["archive_channel_id"]
        )

        if archive_channel is None:
            return

        archive_embed = embed.copy()   

        archive_embed.add_field(
            name="Original Suggestion",
            value=f"[View Original]({message.jump_url})",
            inline=False
            )

        await archive_channel.send(embed=archive_embed)

##Helper function that retrieves suggestion messsage and embed by suggestion ID
async def get_suggestion_message_by_id(
    suggestion_id: int,
    interaction: discord.Interaction
):
    record = await get_suggestion_record(
        interaction.guild.id,
        suggestion_id
    )

    if record is None:
        await interaction.followup.send(
            f"No suggestion found with ID #{suggestion_id:03d}.",
            ephemeral=True
        )
        return None, None

    if record["message_id"] is None:
        await interaction.followup.send(
            f"Suggestion #{suggestion_id:03d} has no Discord message attached to it.",
            ephemeral=True
        )
        return None, None

    channel = interaction.guild.get_channel(
        record["channel_id"]
    )

    if channel is None:
        await interaction.followup.send(
            "I couldn't find the channel for that suggestion.",
            ephemeral=True
        )
        return None, None

    try:
        message = await channel.fetch_message(
            record["message_id"]
        )
    except discord.NotFound:
        await interaction.followup.send(
            f"I couldn't find the message for Suggestion #{suggestion_id:03d}.",
            ephemeral=True
        )
        return None, None

    if not message.embeds:
        await interaction.followup.send(
            "That suggestion doesn't contain a valid embed.",
            ephemeral=True
        )
        return None, None

    embed = message.embeds[0]

    return message, embed

bot.run(TOKEN)
