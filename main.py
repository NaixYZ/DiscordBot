import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timezone, timedelta
import random
import asyncio

# Config load
with open("config.json", "r", encoding="utf-8") as config_file:
    config = json.load(config_file)

TOKEN = config["TOKEN"]
GUILD_ID = config["GUILD_ID"]
ALLOWED_ROLES = config.get("ALLOWED_ROLES", [])  # Roles that are allowed to execute commands

# ID des Voice-Channels für den Member Count
VOICE_CHANNEL_ID = 1354056851708182610  # Ersetze dies durch die tatsächliche ID deines Voice-Channels

# Load cheat roles from config
CHEAT_ROLES = {
    "Neverloose": {"name": "Neverloose", "emoji": "🔥", "id": 1353664202392342528},
    "Fatality": {"name": "Fatality", "emoji": "💀", "id": 1353664399054864444},
    "Nixware": {"name": "Nixware", "emoji": "⚙️", "id": 1353673417961902081},
    "Kidua": {"name": "Kidua", "emoji": "⚔️", "id": 1353664328695414876},
    "Oxide": {"name": "Oxide", "emoji": "🧪", "id": 1353664105654911107},
    "Gamesense": {"name": "Gamesense", "emoji": "🎮", "id": 1353664007319457823},
    "Iniuria": {"name": "Iniuria", "emoji": "🛡️", "id": 1342247941103947786},
    "F0xyz.net": {"name": "F0xyz.net", "emoji": "🛡️", "id": 1353664574057873488},
    "ech0.cc": {"name": "ech0.cc", "emoji": "🛡️", "id": 1353664485747069029},
    "memesense": {"name": "memesense", "emoji": "🛡️", "id": 1353664711476117559}
}

# Reaction Roles
REACTION_ROLES = {role_data["name"]: role_data["id"] for role_data in CHEAT_ROLES.values()}

intents = discord.Intents.default()
intents.messages = True  # Allows message deletion
intents.message_content = True
intents.guilds = True
intents.members = True  # Required for kick and ban commands
intents.reactions = True  # Enable reactions

bot = commands.Bot(command_prefix="!", intents=intents)

warns = {}
debug_mode = False  # Default no detailed errors

# Log channel name
LOG_CHANNEL_NAME = "logs"
VERIFY_CHANNEL_NAME = "verify"

# Ticket system variables
TICKET_CATEGORY_NAME = "Tickets"
ARCHIVE_CATEGORY_NAME = "Archived Tickets"

# Channels to nuke
CHANNELS_TO_NUKE = ["trashtalk", "afd talk", "media"]

async def nuke_channels(guild):
    for channel_name in CHANNELS_TO_NUKE:
        channel = discord.utils.get(guild.text_channels, name=channel_name)
        if channel:
            await channel.purge()  # Lösche alle Nachrichten im Channel
            await channel.send("Channel got nuked")  # Sende die Nachricht

@tasks.loop(minutes=1)  # Überprüfe jede Minute
async def nuke_task():
    await bot.wait_until_ready()  # Warte, bis der Bot bereit ist
    now = datetime.now(timezone(timedelta(hours=1)))  # Deutsche Zeit (MEZ/MESZ)
    if (now.hour == 0 or now.hour == 15) and now.minute == 0:  # Überprüfe, ob es 00:00 oder 15:00 Uhr ist
        guild = bot.get_guild(GUILD_ID)  # Hole die Guild
        await nuke_channels(guild)  # Rufe die Nuke-Funktion auf

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support/Question", description="Get help with general support or questions."),
            discord.SelectOption(label="Discord Server Problems", description="Report issues related to the Discord server.")
        ]
        super().__init__(placeholder="Select the type of issue...", options=options, min_values=1, max_values=1, custom_id="ticket_dropdown")  # Added custom_id

    async def callback(self, interaction: discord.Interaction):
        category = discord.utils.get(interaction.guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await interaction.guild.create_category(TICKET_CATEGORY_NAME)
        ticket_channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            topic=f"Ticket created by {interaction.user.name} for {self.values[0]}"
        )

        await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        await ticket_channel.set_permissions(interaction.guild.default_role, read_messages=False)
        view = discord.ui.View()
        view.add_item(CloseTicketButton())
        await ticket_channel.send(f"{interaction.user.mention} created a ticket for **{self.values[0]}**.\n\nPlease describe your issue here.", view=view)
        await interaction.response.send_message(f"Your ticket has been created in {ticket_channel.mention}.", ephemeral=True)


class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")

    async def callback(self, interaction: discord.Interaction):
        # Remove the user from the channel permissions
        await interaction.channel.set_permissions(interaction.user, read_messages=False, send_messages=False)

        archive_category = discord.utils.get(interaction.guild.categories, name=ARCHIVE_CATEGORY_NAME)
        if archive_category is None:
            archive_category = await interaction.guild.create_category(ARCHIVE_CATEGORY_NAME)
        await interaction.channel.edit(category=archive_category, sync_permissions=True)
        await interaction.channel.send("This ticket has been closed and archived.")
        await interaction.response.send_message("Ticket closed and archived.", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


@bot.command()
async def ticket(ctx):
    view = TicketView()
    await ctx.send("Please select the type of issue you're experiencing:", view=view)


class VerifyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Verify", style=discord.ButtonStyle.primary, custom_id="verify_button")  # custom_id hinzugefügt

    async def callback(self, interaction: discord.Interaction):
        # Generate a simple math problem
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        answer = num1 + num2

        # Send the captcha message
        await interaction.response.send_message(f"Please solve the captcha: What is {num1} + {num2}?", ephemeral=True)

        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            # Wait for the user's answer
            msg = await bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("Timeout! Please try again.", ephemeral=True)
            return

        # Check the answer
        if msg.content.isdigit() and int(msg.content) == answer:
            role = discord.utils.get(interaction.guild.roles, name="user")  # Ensure the role name is correct
            if role:
                await interaction.user.add_roles(role)
                await interaction.user.send(f"Congratulations, {interaction.user.mention}! You have successfully solved the captcha and received the role {role.mention}.")
                await msg.delete()  # Delete the answer message
            else:
                await interaction.followup.send("The role @user does not exist.", ephemeral=True)
        else:
            await interaction.followup.send("Wrong answer! Please try again.", ephemeral=True)


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VerifyButton())


class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Keine Zeitbegrenzung


async def create_log_channel(guild):
    # Check if the log channel already exists
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel is None:
        # Create the log channel if it doesn't exist
        log_channel = await guild.create_text_channel(LOG_CHANNEL_NAME)
    return log_channel


@bot.event
async def on_ready():
    nuke_task.start()  # Starte den Nuke-Task
    await bot.change_presence(activity=discord.Game(name="Visualise Systems"), status=discord.Status.idle)
    bot.add_view(VerifyView())  # Add the persistent view for the verify button
    bot.add_view(TicketView())  # Add the persistent view for the ticket system
    bot.add_view(CombinedRoleView())  # Add the persistent view for the reaction roles
    print(f"Logged in as {bot.user}")

    # Create log channel if it doesn't exist
    guild = bot.get_guild(GUILD_ID)
    await create_log_channel(guild)

    # Clear old messages in the verify channel and send a new one
    verify_channel = discord.utils.get(guild.text_channels, name=VERIFY_CHANNEL_NAME)
    if verify_channel:
        await verify_channel.purge()  # Lösche alle alten Nachrichten im #verify-Kanal
        # Sende eine neue Verifizierungsnachricht mit dem Button
        view = VerifyView()
        await verify_channel.send("Click the button to solve the captcha:", view=view)

    # Update member count in the voice channel
    await update_member_count(guild)

@bot.event
async def on_member_join(member):
    guild = member.guild
    await update_member_count(guild)

@bot.event
async def on_member_remove(member):
    guild = member.guild
    await update_member_count(guild)

async def update_member_count(guild):
    voice_channel = guild.get_channel(VOICE_CHANNEL_ID)
    if voice_channel:
        member_count = guild.member_count  # Gesamtanzahl der Mitglieder im Server
        await voice_channel.edit(name=f'Mitglieder: {member_count}')  # Ändere den Namen des Voice-Channels

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Log messages and GIFs to the log channel
    guild = message.guild
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        if message.content:
            embed = discord.Embed(
                title="Message Logged",
                description=f"**User       :** {message.author}\n**Message:** {message.content}\n**Channel:** {message.channel.mention}",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
            await log_channel.send(embed=embed)

        if message.attachments:
            for attachment in message.attachments:
                if attachment.url.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    embed = discord.Embed(
                        title="Image Logged",
                        description=f"**User       :** {message.author}\n**Image:** {attachment.url}\n**Channel:** {message.channel.mention}",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text=f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
                    await log_channel.send(embed=embed)

    await bot.process_commands(message)


async def log_command(ctx):
    # Log command execution to the log channel
    guild = ctx.guild
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(
            title="Command Executed",
            description=f"**User       :** {ctx.author}\n**Command:** {ctx.message.content}\n**Channel:** {ctx.channel.mention}",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        await log_channel.send(embed=embed)


# Permission check
def has_permission(ctx):
    return any(role.name in ALLOWED_ROLES for role in ctx.author.roles)


@bot.command()
async def command(ctx):
    commands_list = [command.name for command in bot.commands]
    commands_string = "\n".join(commands_list)
    await ctx.send(f"Available commands:\n{commands_string}")

@bot.command()
@commands.has_permissions(manage_channels=True)  # Sicherstellen, dass der Benutzer die Berechtigung hat, Channels zu verwalten
async def nukeall(ctx):
    """Nuke specified channels immediately."""
    guild = ctx.guild
    await nuke_channels(guild)  # Rufe die Nuke-Funktion auf
    await ctx.send("Die angegebenen Channels wurden nuked!")  # Bestätigungsnachricht

@bot.command()
async def say(ctx, *, message: str):
    if not has_permission(ctx):
        await ctx.send("You are not authorized to use this command!", delete_after=5)
        return
    await log_command(ctx)  # Log the command... # Create an embed object
    embed = discord.Embed(description=message, color=discord.Color.blue())
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()


@bot.command()
async def clear(ctx, count: int):
    await log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to use this command!", delete_after=5)
        return
    deleted = await ctx.channel.purge(limit=count + 1)
    await ctx.send(f"{len(deleted) - 1} messages have been deleted!", delete_after=5)


@bot.command()
async def kick(ctx, member: discord.Member, *, reason="No reason given"):
    await log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to kick members!", delete_after=5)
        return
    if ctx.guild.me.guild_permissions.kick_members:
        await member.kick(reason=reason)
        await ctx.send(f"{member.mention} was temporarily kicked!", delete_after=5)
    else:
        await ctx.send("I do not have permission to kick members!", delete_after=5)
    await ctx.message.delete()


@bot.command()
async def ban(ctx, member: discord.Member, *, reason="No reason given"):
    await log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to ban members!", delete_after=5)
        return
    if ctx.guild.me.guild_permissions.ban_members:
        await member.ban(reason=reason)
        await ctx.send(f"{member.mention} was banned permanently!", delete_after=5)
    else:
        await ctx.send("I do not have permission to ban members!", delete_after=5)
    await ctx.message.delete()


@bot.command()
async def warn(ctx, member: discord.Member, *, reason="No reason given"):
    await log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to warn members!", delete_after=5)
        return
    user_id = str(member.id)
    warns[user_id] = warns.get(user_id, 0) + 1
    await member.send(f"You have been warned in {ctx.guild.name}. (Warning {warns[user_id]}/3) Reason: {reason}")
    await ctx.send(f"{member.mention} has been warned! (Warning {warns[user_id]}/3) Reason: {reason}")
    if warns[user_id] >= 3:
        if ctx.guild.me.guild_permissions.ban_members:
            await member.ban(reason="Too many warnings (3/3)")
            await ctx.send(f"{member.mention} has been banned for receiving 3 warnings!")
            warns.pop(user_id)
        else:
            await ctx.send("I do not have permission to ban members!")


@bot.command()
async def unwarn(ctx, member: discord.Member):
    await log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to remove warnings!", delete_after=5)
        return
    user_id = str(member.id)
    if user_id in warns and warns[user_id] > 0:
        warns[user_id] -= 1
        await member.send(
            f"A warning has been removed from your account on {ctx.guild.name}. You now have {warns[user_id]}/3 warnings.")
        await ctx.send(f"{member.mention} now has {warns[user_id]}/3 warnings.")
    else:
        await ctx.send(f"{member.mention} has no warnings.")


@bot.command()
async def debugg(ctx):
    global debug_mode
    debug_mode = not debug_mode
    status = "enabled" if debug_mode else "disabled"
    await ctx.send(f"Debug mode has been {status}.")


# Combined Role Selection Dropdown
class CombinedRoleSelect(discord.ui.Select):
    def __init__(self):
        options = []
        # Add cheat roles to the dropdown
        for role_data in CHEAT_ROLES.values():
            options.append(discord.SelectOption(label=role_data["name"], value=f"cheat_{role_data['id']}", description=f"Select this role to receive {role_data['name']}."))

        super().__init__(placeholder="Select a role...", options=options, min_values=1, max_values=1, custom_id="combined_role_select")  # Added custom_id

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        role_type, selected_role_id = selected_value.split("_")
        guild = interaction.guild
        role = guild.get_role(int(selected_role_id))
        user = interaction.user

        if role:
            if role in user.roles:
                await user.remove_roles(role)
                await interaction.response.send_message(f"The role **{role.name}** has been removed from you.", ephemeral=True)
            else:
                await user.add_roles(role)
                await interaction.response.send_message(f"The role **{role.name}** has been assigned to you.", ephemeral=True)
        else:
            await interaction.response.send_message("The role does not exist.", ephemeral=True)


class CombinedRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CombinedRoleSelect())


@bot.command()
async def setup_combined_reaction_roles(ctx):
    view = CombinedRoleView()
    await ctx.send("Select a role from the dropdown menu:", view=view)


# Reaction Roles Handling
@bot.event
async def on_raw_reaction_add(payload):
    await handle_reaction(payload, add=True)


@bot.event
async def on_raw_reaction_remove(payload):
    await handle_reaction(payload, add=False)


async def handle_reaction(payload, add):
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    channel = guild.get_channel(payload.channel_id)
    if channel is None:
        return

    message = await channel.fetch_message(payload.message_id)
    if message is None:
        return

    emoji = payload.emoji.name

    # Debugging output
    print(f"Reaction added by {payload.user_id} with emoji {emoji}")

    # Check if the reaction is for cheat roles
    for key, role_data in CHEAT_ROLES.items():
        if emoji == role_data["emoji"]:
            role_id = role_data.get("id")  # Get the role ID from config
            if role_id:
                role = guild.get_role(role_id)  # Get the role by ID
            else:
                role_name = role_data["name"]
                role = discord.utils.get(guild.roles, name=role_name)

            if role:
                member = guild.get_member(payload.user_id)
                if member:
                    if add:
                        await member.add_roles(role)  # Corrected method
                        print(f"Added role {role.name} to {member.name}")
                    else:
                        await member.remove_roles(role)  # Corrected method
                        print(f"Removed role {role.name} from {member.name}")
                    return  # Exit after processing


@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")


bot.run(TOKEN)
