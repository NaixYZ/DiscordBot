import discord
from discord.ext import commands
import json
from datetime import datetime, timezone

# Config load
with open("config.json", "r") as config_file:
    config = json.load(config_file)

TOKEN = config["TOKEN"]
GUILD_ID = config["GUILD_ID"]
ALLOWED_ROLES = config.get("ALLOWED_ROLES", [])  # Roles that are allowed to execute commands

intents = discord.Intents.default()
intents.messages = True  # Allows message deletion
intents.message_content = True
intents.guilds = True
intents.members = True  # Required for kick and ban commands

bot = commands.Bot(command_prefix="!", intents=intents)

warns = {}
debug_mode = False  # Default no detailed errors


def log_command(ctx):
    with open("logs.txt", "a") as log_file:
        log_file.write(f"[{datetime.now(timezone.utc)}] {ctx.author} executed {ctx.message.content}.\n")


# Permission check
def has_permission(ctx):
    return any(role.name in ALLOWED_ROLES for role in ctx.author.roles)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Visualise Systems"), status=discord.Status.idle)
    print(f"Logged in as {bot.user}")


@bot.command()
async def clear(ctx, anzahl: int):
    log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to use this command!", delete_after=5)
        return
    deleted = await ctx.channel.purge(limit=anzahl + 1)
    await ctx.send(f"{len(deleted) - 1} messages have been deleted!", delete_after=5)


@bot.command()
async def kick(ctx, member: discord.Member, *, reason="No reason given"):
    log_command(ctx)
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
    log_command(ctx)
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
    log_command(ctx)
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
    log_command(ctx)
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
async def say(ctx, *, message: str):
    log_command(ctx)
    if not has_permission(ctx):
        await ctx.send("You are not authorized to use this command!", delete_after=5)
        return
    await ctx.send(message)
    await ctx.message.delete()


class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", value="support"),
            discord.SelectOption(label="Config Support", value="config"),
        ]
        super().__init__(placeholder="Choose a ticket category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        category_name = self.values[0]
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            category = await guild.create_category("Tickets")
        ticket_channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", category=category)

        # Mod-Rolle search
        mod_role = discord.utils.get(guild.roles, name="mod")  # Ensure role name is correct

        # Check if the "mod" role exists
        if mod_role:
            await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            await ticket_channel.send(
                f"{interaction.user.mention}, a ticket has been created. {mod_role.mention} A team member will be in touch soon.")
        else:
            await ticket_channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
            await ticket_channel.send(
                f"{interaction.user.mention}, a ticket has been created. A team member will be in touch soon.")
        # Send initial message with close button
        view = discord.ui.View()
        view.add_item(CloseTicketButton())
        await ticket_channel.send(f".", view=view)
        await interaction.response.send_message(
            f"Ticket for {category_name} was created: {ticket_channel.mention}", ephemeral=True)


class CloseTicketButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.danger, label="Close Ticket")

    async def callback(self, interaction: discord.Interaction):
        # Find the "Tickets" category
        category = discord.utils.get(interaction.guild.categories, name="Tickets")

        # Delete the channel
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await interaction.channel.delete()


@bot.command()
async def ticket(ctx):
    view = discord.ui.View()
    view.add_item(TicketSelect())
    await ctx.send("Please select a ticket category:", view=view)


@bot.command()
async def debugg(ctx):
    global debug_mode
    debug_mode = not debug_mode
    status = "enabled" if debug_mode else "disabled"
    await ctx.send(f"Debug mode has been {status}.")


bot.run(TOKEN)
