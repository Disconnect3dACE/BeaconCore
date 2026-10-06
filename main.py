import os
import discord
import re
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from database import init_database, get_guild_settings


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 997417956843716629

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!", 
    intents=intents
)

## Suggestion Modal and Setup View Classes
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
        settings = await get_guild_settings(interaction.guild.id)

        if settings is None:
            await interaction.response.send_message(
                "This server has not been configured yet.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(
            settings["suggestion_channel_id"]
        )

        if channel is None:
            await interaction.response.send_message(
                "I couldn't find the configured suggestion channel.",
                ephemeral=True
            )
            return   

        embed = discord.Embed(
            title="New Suggestion",
            description=self.suggestion.value
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

        await thread.send(
        "Use this thread to discuss the current suggestion."
        )
        

        await interaction.response.send_message(
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

##Persistent view setup to keep the button active even after bot restarts
async def setup_hook():
    await init_database()
    bot.add_view(SetupView())

bot.setup_hook=setup_hook

##On ready event and command syncing
@bot.event
async def on_ready():

    guild = discord.Object(id=GUILD_ID)

    bot.tree.copy_global_to(guild=guild)
    synced = await bot.tree.sync(guild=guild)

    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Synced {len(synced)} commands")

##Ping command to check if the bot is online
@bot.tree.command(name="ping", description="Check to see if the bot is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

##Basic setup command to send the setup message with the button, nothing detailed, just a simple command to send the setup message with the button
@bot.tree.command(name="setup", description="Basic bot setup")
async def setup(interaction:discord.Interaction):
    view = SetupView()

    await interaction.response.send_message(
        "Need Something?",
        view=view
    )

##Helper functions for suggestion commands
async def get_suggestion_message(message_link: str, interaction: discord.Interaction):
    match = re.search(
        r"discord\.com/channels/(\d+)/(\d+)/(\d+)",
        message_link
    )

    if not match:
        await interaction.response.send_message(
            "That doesn't look like a valid Discord message link.",
            ephemeral=True
        )
        return None, None

    guild_id, channel_id, message_id = map(int, match.groups())

    if guild_id != interaction.guild.id:
        await interaction.response.send_message(
            "That message is from a different server.",
            ephemeral=True
        )
        return None, None

    channel = interaction.guild.get_channel(channel_id)

    if channel is None:
        await interaction.response.send_message(
            "I couldn't find that channel.",
            ephemeral=True
        )
        return None, None

    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound:
        await interaction.response.send_message(
            "I couldn't find that message.",
            ephemeral=True
        )
        return None, None

    if message.author != bot.user:
        await interaction.response.send_message(
            "That message was not created by Help Desk.",
            ephemeral=True
        )
        return None, None

    if not message.embeds:
        await interaction.response.send_message(
        "That message doesn't contain a suggestion embed.",
        ephemeral=True
    )
        return None, None

    embed = message.embeds[0]

    if embed.title != "New Suggestion":
        await interaction.response.send_message(
        "That doesn't look like a suggestion post.",
        ephemeral=True
    )
        return None, None

    return message, embed

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

##Helper function to check if a suggestion has a final; status (approved or denied)
def suggestion_is_decided(embed: discord.Embed):
    final_statuses = ["✅ Approved", "❌ Denied"]

    for field in embed.fields:
        if field.name == "Status" and field.value in final_statuses:
            return True
        
    return False

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

#Approve and Deny commands for suggestions, only usable by users with manage_messages permission
@bot.tree.command(
    name="approve",
    description="Approve a suggestion"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def approve(
    interaction: discord.Interaction,
    message_link: str
):
    message, embed = await get_suggestion_message(
        message_link, 
        interaction
    )

    if message is None:
        return

    if suggestion_is_decided(embed):   
        await interaction.response.send_message(
            "This suggestion has already been decided.",
            ephemeral=True
        )
        return
    
    set_status(embed, "✅ Approved")
    await message.edit(embed=embed)

    await interaction.response.send_message(
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

@bot.tree.command(
    name="deny",
    description="Deny a suggestion"
)
@app_commands.checks.has_permissions(manage_messages=True)
async def deny(
    interaction: discord.Interaction,
    message_link: str
):
    message, embed = await get_suggestion_message(
        message_link, 
        interaction
    )

    if message is None:
        return
    
    if suggestion_is_decided(embed):
        await interaction.response.send_message(
            "This suggestion has already been decided.",
            ephemeral=True
        )
        return

    set_status(embed, "❌ Denied")
    await message.edit(embed=embed)

    await interaction.response.send_message(
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

bot.run(TOKEN)
