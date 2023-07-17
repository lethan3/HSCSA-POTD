import asyncio
import math
import os
import random
import string
from datetime import datetime
from typing import Dict, List, Union, Tuple

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord import Embed, Color
from discord.ext import commands
from dotenv import load_dotenv

import cf_api
import database
from constants import POTD_PROBLEMS, POTD_GUILD, POTD_ANNOUNCE

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())

global db, cf

cf_colors: Dict[str, int] = {
    "unrated": 0x000000,
    "newbie": 0x808080,
    "pupil": 0x008000,
    "specialist": 0x03A89E,
    "expert": 0x0000FF,
    "candidate master": 0xAA00AA,
    "master": 0xFF8C00,
    "international master": 0xF57500,
    "grandmaster": 0xFF3030,
    "international grandmaster": 0xFF0000,
    "legendary grandmaster": 0xCC0000,
}


@bot.event
async def on_ready():
    global db, cf
    print(f"{bot.user} has connected to Discord")

    db = database.Database()
    cf = cf_api.CodeforcesAPI()
    print("Database and CF API initialized")

    await update_problemset()
    print("Problemset updated")

    if db.get_potd() is None:
        await select_potd()
    # await update_solvers()
    # print('Solvers updated')

    scheduler = AsyncIOScheduler()
    scheduler.add_job(select_potd, CronTrigger(hour="0"))
    scheduler.add_job(update_solvers, "interval", minutes=1)
    scheduler.start()


@bot.command(name="identify_handle", help="Set your CF handle")
async def identify_handle(ctx: commands.Context, handle: str = None):
    if handle is None:
        await ctx.send("Please specify a Codeforces handle.")
        return
    if db.get_handle(ctx.guild.id, ctx.author.id):
        await ctx.send(
            f"Your handle is already set to {db.get_handle(ctx.guild.id, ctx.author.id)}, "
            f"ask an admin or mod to remove it first and try again."
        )
        return

    data = await cf.check_handle(handle)
    if not data[0]:
        await ctx.send(data[1])
        return

    data = data[1]
    handle = data["handle"]

    # 2 discord users setting same handle
    handles = list(filter(lambda x: x[2] == handle, db.get_all_handles(ctx.guild.id)))
    if len(handles):
        await ctx.send("That handle is already in use")
        return

    res = "".join(random.choices(string.ascii_uppercase + string.digits, k=15))
    await ctx.send(
        f"Please change your first name on https://codeforces.com/settings/social to "
        f"`{res}` within 30 seconds {ctx.author.mention}"
    )
    await asyncio.sleep(30)

    if res != await cf.get_first_name(handle):
        await ctx.send(f"Unable to set handle, please try again {ctx.author.mention}")
        return

    member = ctx.author
    if "rating" not in data:
        rating = 0
        rank = "unrated"
    else:
        rating = data["rating"]
        rank = data["rank"]
    db.add_handle(ctx.guild.id, member.id, handle, rating)
    embed = (
        Embed(
            description=f"Handle for {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})",
            color=Color(cf_colors[rank.lower()]),
        )
        .add_field(name="Rank", value=f"{rank}", inline=True)
        .add_field(name="Rating", value=f"{rating}", inline=True)
        .set_thumbnail(url=f"{data['titlePhoto']}")
    )
    await ctx.send(embed=embed)


def has_admin_privilege(ctx: commands.Context) -> bool:
    if ctx.channel.permissions_for(ctx.author).manage_guild:
        return True
    for role in ["POTD Manager"]:
        if role.lower() in [x.name.lower() for x in ctx.author.roles]:
            return True
    return False


@bot.command(
    name="set_handle", help="Set someone's handle (Admin/Mod/Lockout Manager only)"
)
async def set_handle(
    ctx: commands.Context, member: discord.Member = None, handle: str = None
):
    if handle is None or member is None:
        await ctx.send("Please specify a user and Codeforces handle.")
        return
    if not has_admin_privilege(ctx):
        await ctx.send(
            f"{ctx.author.mention} you require 'manage server' permission or the POTD Manager role to use this command"
        )
        return

    data = await cf.check_handle(handle)
    if not data[0]:
        await ctx.send(data[1])
        return

    handle = data[1]["handle"]
    if db.get_handle(ctx.guild.id, member.id):
        await ctx.send(
            f"Handle for user {member.mention} already set to {db.get_handle(ctx.guild.id, member.id)}"
        )
        return
    # 2 discord users setting same handle
    handles = list(filter(lambda x: x[2] == handle, db.get_all_handles(ctx.guild.id)))
    if len(handles):
        await ctx.send("That handle is already in use")
        return

    # all conditions met
    data = data[1]
    if "rating" not in data:
        rating = 0
        rank = "unrated"
    else:
        rating = data["rating"]
        rank = data["rank"]
    db.add_handle(ctx.guild.id, member.id, handle, rating)
    embed = (
        Embed(
            description=f"Handle for user {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})",
            color=Color(cf_colors[rank.lower()]),
        )
        .add_field(name="Rank", value=f"{rank}", inline=True)
        .add_field(name="Rating", value=f"{rating}", inline=True)
        .set_thumbnail(url=f"{data['titlePhoto']}")
    )
    await ctx.send(embed=embed)


@bot.command(name="get_handle", help="Get your CF handle")
async def get_handle(ctx: commands.Context, member: discord.Member = None):
    if member is None:
        member = ctx.author
    if not db.get_handle(ctx.guild.id, member.id):
        await ctx.send(f"Handle for {member.mention} is not set currently")
        return
    handle = db.get_handle(ctx.guild.id, member.id)
    data = await cf.check_handle(handle)
    if not data[0]:
        await ctx.send(data[1])
        return

    data = data[1]
    if "rating" not in data:
        rating = 0
        rank = "unrated"
    else:
        rating = data["rating"]
        rank = data["rank"]
    embed = (
        Embed(
            description=f"Handle for {member.mention} currently set to [{handle}](https://codeforces.com/profile/{handle})",
            color=Color(cf_colors[rank.lower()]),
        )
        .add_field(name="Rank", value=f"{rank}", inline=True)
        .add_field(name="Rating", value=f"{rating}", inline=True)
        .set_thumbnail(url=f"{data['titlePhoto']}")
    )
    await ctx.send(embed=embed)


@bot.command(
    name="remove_handle",
    help="Remove someone's handle (Admin/Mod/Lockout Manager only)",
)
async def remove_handle(ctx: commands.Context, member: discord.Member = None):
    if member is None:
        await ctx.send("Please specify a member.")
    if not has_admin_privilege(ctx):
        await ctx.send(
            f"{ctx.author.mention} you require 'manage server' permission or the POTD Manager role to use this command"
        )
        return
    if not db.get_handle(ctx.guild.id, member.id):
        await ctx.send(f"Handle for {member.mention} not set")
        return

    db.remove_handle(ctx.guild.id, member.id)
    await ctx.send(
        embed=Embed(
            description=f"Handle for {member.mention} removed successfully",
            color=Color.green(),
        )
    )


def is_non_standard(contest_name: str) -> bool:
    names = [
        "wild",
        "fools",
        "unrated",
        "surprise",
        "unknown",
        "friday",
        "q#",
        "testing",
        "marathon",
        "kotlin",
        "onsite",
        "experimental",
        "abbyy",
    ]
    for x in names:
        if x in contest_name.lower():
            return True
    return False


async def update_problemset():
    contest_id = [x[0] for x in db.get_contests_id()]
    problem_id = [x.id for x in db.get_problems()]
    contest_list = await cf.get_contest_list()
    problem_list = await cf.get_problem_list()

    mapping = {}

    con_cnt, prob_cnt = 0, 0

    for contest in contest_list:
        mapping[contest["id"]] = contest["name"]
        if (
            contest["id"] not in contest_id
            and contest["phase"] == "FINISHED"
            and not is_non_standard(contest["name"])
        ):
            con_cnt += 1
            db.add_contest(contest["id"], contest["name"])

    for problem in problem_list:
        if (
            problem["contestId"] in mapping
            and not is_non_standard(mapping[problem["contestId"]])
            and "rating" in problem
            and problem["contestId"] not in problem_id
        ):
            prob_cnt += 1
            db.add_problem(
                problem["contestId"],
                problem["index"],
                problem["name"],
                problem["type"],
                problem["rating"],
                False,
            )


async def find_problem(rating) -> List[Union[bool, str]]:
    all_problems = db.get_problems()

    problem = None
    options = [p for p in all_problems if p.rating == rating and not p.used]
    weights = [int(p.id * math.sqrt(p.id)) for p in options]
    if options:
        return random.choices(options, weights, k=1)
    else:
        return [False, f"Not enough problems with rating {rating} left!"]


potd_difficulties: List[int] = [800, 1200, 900, 1300, 1000, 1600, 1400]


async def select_potd():
    while datetime.today().hour == 23:
        pass
    diff = potd_difficulties[datetime.today().weekday()]
    problem = (await find_problem(diff))[0]
    db.add_potd(id=problem.id, index=problem.index, name=problem.name)
    db.set_used(id=problem.id, index=problem.index, name=problem.name)
    msg: discord.Message = await bot.get_channel(POTD_PROBLEMS).send(
        "<@&1120846668833771560>",
        embed=Embed(
            title="POTD " + datetime.today().strftime("%m/%d/%Y"),
            description=f"\n[{problem.name}](https://codeforces.com/contest/{problem.id}/problem/{problem.index})",
            color=Color.blue(),
        ),
    )
    await msg.publish()


@bot.command(name="get_potd", help="Get the current POTD")
async def get_potd(ctx: commands.Context):
    problem = db.get_potd()
    await ctx.send(
        embed=Embed(
            title="POTD " + datetime.today().strftime("%m/%d/%Y"),
            description=f"\n[{problem.name}](https://codeforces.com/contest/{problem.id}/problem/{problem.index})",
            color=Color.blue(),
        )
    )


async def check_solved(handle, id, index) -> bool:
    subs = await cf.get_user_problems(handle, 50)
    if not subs[0]:
        return False
    for x in subs[1]:
        if x.id == int(id) and x.index == index:
            if x.verdict == "OK":
                return True
    return False


async def update_solvers():
    problem = db.get_potd()
    if problem is None:
        return
    users = db.get_all_handles(POTD_GUILD)
    for user in users:
        if await check_solved(
            user[2], problem.id, problem.index
        ) and not db.check_user_potd(user[2]):
            db.set_user_potd(user[2])
            msg: discord.Message = await bot.get_channel(POTD_ANNOUNCE).send(
                f"Congratulations to <@{user[1]}> for solving POTD "
                + datetime.today().strftime("%m/%d/%Y")
                + "!"
            )
            await msg.publish()
            await msg.add_reaction("<:orz:1105018917828698204>")
    print("Solvers updated")


@bot.command(name="update_potd", help="Update list of POTD solvers")
async def update_potd(ctx: commands.Context):
    await update_solvers()
    success_embed: Embed = Embed(title="POTD solvers updated", color=Color.green())
    await ctx.send(embed=success_embed)


def format_number(number: int) -> str:
    """Format an :class:`int` with commas.

    Example:

    ```python
    >>> format_number(1000)
    "1,000"
    ```

    Parameters
    ----------
    number: :class:`int`
        The number to format.

    Returns
    -------
    :class:`str`
        The formatted number with commas.
    """
    return "{:,}".format(number)


@bot.command(
    name="streak_leaderboard", help="Show leaderboard of current streak holders"
)
async def streak_leaderboard(ctx: commands.Context):
    users = db.get_all_handles()
    user_lb = []
    for user in users:
        streak = 0
        for i in range(len(user) - 1, 3, -1):
            if not user[i]:
                if i == len(user) - 1:
                    continue
                else:
                    break
            streak += 1
        user_lb.append([streak, user[2]])
    user_lb.sort()
    user_lb.reverse()
    curr_place = 1
    lb_strings = []
    for i in range(len(user_lb)):
        if i == 0 or user_lb[i - 1][0] != user_lb[i][0]:
            curr_place = i + 1
        lb_strings.append(
            str(curr_place)
            + "\U0000200D. "
            + user_lb[i][1]
            + " - "
            + format_number(user_lb[i][0])
            + " day"
            + ("s" if user_lb[i][0] != 1 else "")
        )
    await ctx.send(
        embed=Embed(
            title="Current Streak Leaderboard",
            description=discord.utils.escape_markdown("\n".join(lb_strings)),
            color=Color.orange(),
        )
    )


@bot.command(name="solves_leaderboard", help="Show leaderboard of problems solved")
async def solves_leaderboard(ctx: commands.Context):
    users = db.get_all_handles()
    user_lb = []
    for user in users:
        solved = 0
        for i in range(len(user) - 1, 3, -1):
            solved += user[i]
        user_lb.append([solved, user[2]])
    user_lb.sort()
    user_lb.reverse()
    curr_place = 1
    lb_strings = []
    for i in range(len(user_lb)):
        if i == 0 or user_lb[i - 1][0] != user_lb[i][0]:
            curr_place = i + 1
        lb_strings.append(
            str(curr_place)
            + "\U0000200D. "
            + user_lb[i][1]
            + " - "
            + format_number(user_lb[i][0])
            + " problem"
            + ("s" if user_lb[i][0] != 1 else "")
        )
    await ctx.send(
        embed=Embed(
            title="Current Solves Leaderboard",
            description=discord.utils.escape_markdown("\n".join(lb_strings)),
            color=Color.purple(),
        )
    )


if __name__ == "__main__":
    bot.run(TOKEN)
