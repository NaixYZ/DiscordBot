import discord
from discord.ext import commands
import json
from datetime import datetime, timezone
import random
import asyncio

# Config load
with open("config.json", "r", encoding="utf-8") as config_file:
    config = json.load(config_file)

TOKEN = config["TOKEN"]
GUILD_ID = config["GUILD_ID"]
ALLOWED_ROLES = config.get("ALLOWED_ROLES", [])  # Roles that are allowed to execute commands

# Load cheat roles from config
CHEAT_ROLES = config.get("CHEAT_ROLES", {})

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

async def create_log_channel(guild):
    # Check if the log channel already exists
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel is None:
        # Create the log channel if it doesn't exist
        log_channel = await guild.create_text_channel(LOG_CHANNEL_NAME)
    return log_channel

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Visualise Systems"), status=discord.Status.idle)
    print(f"Logged in as {bot.user}")

    # Create log channel if it doesn't exist
    guild = bot.get_guild(GUILD_ID)
    await create_log_channel(guild)

    # Clear old messages in the verify channel and send a new one
    verify_channel = discord.utils.get(guild.text_channels, name=VERIFY_CHANNEL_NAME)
    if verify_channel:
        await verify_channel.purge()  # Lösche alle alten Nachrichten im #verify-Kanal

        # Sende eine neue Verifizierungsnachricht mit dem Button
        verify_button = discord.ui.Button(label="Verify", style=discord.ButtonStyle.primary)

        async def button_callback(interaction):
            # Generate a simple math problem
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
            answer = num1 + num2

            # Send the captcha message
            await interaction.response.send_message(f"Please solve the captcha: What is {num1} + {num2}?", ephemeral=True)

            def check(m):
                return m.author == interaction.user and m.channel == verify_channel

            try:
                # Wait for the user's answer
                msg = await bot.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                await verify_channel.send("Timeout! Please try again.")
                return

            # Check the answer
            if msg.content.isdigit() and int(msg.content) == answer:
                role = discord.utils.get(guild.roles, name="user")  # Ensure the role name is correct
                if role:
                    await interaction.user.add_roles(role)
                    await interaction.user.send(f"Congratulations, {interaction.user.mention}! You have successfully solved the captcha and received the role {role.mention}.")
                    await msg.delete()  # Delete the answer message
                else:
                    await verify_channel.send("The role @user does not exist.")
            else:
                await verify_channel.send("Wrong answer! Please try again.")

        verify_button.callback = button_callback

        # Create a view and add the button
        view = discord.ui.View()
        view.add_item(verify_button)

        # Send the message with the button
        await verify_channel.send("Click the button to solve the captcha:", view=view)

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
                description=f"**User           :** {message.author}\n**Message:** {message.content}\n**Channel:** {message.channel.mention}",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
            await log_channel.send(embed=embed)
        if message.attachments:
            for attachment in message.attachments:
                if attachment.url.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    embed = discord.Embed(
                        title="Image Logged",
                        description=f"**User           :** {message.author}\n**Image:** {attachment.url}\n**Channel:** {message.channel.mention}",
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
            description=f"**User           :** {ctx.author}\n**Command:** {ctx.message.content}\n**Channel:** {ctx.channel.mention}",
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
async def say(ctx, *, message: str):
    if not has_permission(ctx):
        await ctx.send("You are not authorized to use this command!", delete_after=5)
        return

    await log_command(ctx)  # Log the command

    # Create an embed object
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

        super().__init__(placeholder="Select a role...", options=options, min_values=1, max_values=1)

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
        super().__init__()
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

bot.run(TOKEN)
