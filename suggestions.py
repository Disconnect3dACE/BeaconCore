import discord

from discord.ext import commands
from discord import app_commands

from database import (
    get_guild_settings,
    create_suggestion_record,
    update_suggestion_discord_ids,
    get_suggestion_record,
    update_suggestion_status
)

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

##Register suggestion commands with the bot
def register_suggestion_commands(bot: commands.Bot):

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
