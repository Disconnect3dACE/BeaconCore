import discord

from database import (
    get_guild_settings,
    create_suggestion_record,
    update_suggestion_discord_ids
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
