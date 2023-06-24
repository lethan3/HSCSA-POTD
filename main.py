import os
import random
import asyncio
from datetime import datetime
import math

import discord
from discord import Embed, Color
from discord.ext import commands
from dotenv import load_dotenv

import database
import cf_api

from constants import POTD_PROBLEMS, POTD_GUILD, POTD_ANNOUNCE

from collections import namedtuple
import string

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='.', intents=discord.Intents.all())

global db, cf

cf_colors = {
    'unrated': 0x000000,
    'newbie': 0x808080,
    'pupil': 0x008000,
    'specialist': 0x03a89e,
    'expert': 0x0000ff,
    'candidate master': 0xaa00aa,
    'master': 0xff8c00,
    'international master': 0xf57500,
    'grandmaster': 0xff3030,
    'international grandmaster': 0xff0000,
    'legendary grandmaster': 0xcc0000
}

@bot.event
async def on_ready():
    global db, cf
    print(f'{bot.user} has connected to Discord')

    db = database.Database()
    cf = cf_api.CodeforcesAPI()
    print('Database and CF API initialized')

    await update_problemset()
    print('Problemset updated')

    if (db.get_potd() is None):
        await select_potd()
    # await update_solvers()
    # print('Solvers updated')

    scheduler = AsyncIOScheduler()
    scheduler.add_job(select_potd, CronTrigger(hour="0"))
    scheduler.add_job(update_solvers, 'interval', minutes=1)
    scheduler.start()

@bot.command(name='identify_handle', help='Set your CF handle')
async def identify_handle(ctx, handle: str=None):
    if handle is None:
        await ctx.send("Please specify a Codeforces handle.")
        return
    if db.get_handle(ctx.guild.id, ctx.author.id):
        await ctx.send(f"Your handle is already set to {db.get_handle(ctx.guild.id, ctx.author.id)}, "
                                f"ask an admin or mod to remove it first and try again.")
        return

    data = await cf.check_handle(handle)
    if not data[0]:
        await ctx.send(data[1])
        return
    
    data = data[1]
    handle = data['handle']
    
    # 2 discord users setting same handle
    handles = list(filter(lambda x: x[2] == handle, db.get_all_handles(ctx.guild.id)))
    if len(handles):
        await ctx.send('That handle is already in use')
        return
    
    res = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))
    await ctx.send(
                        f"Please change your first name on https://codeforces.com/settings/social to "
                        f"`{res}` within 30 seconds {ctx.author.mention}")
    await asyncio.sleep(30)

    if res != await cf.get_first_name(handle):
        await ctx.send(f"Unable to set handle, please try again {ctx.author.mention}")
        return

    member = ctx.author
    if "rating" not in data:
        rating = 0
        rank = "unrated"
    else:
        rating = data['rating']
        rank = data['rank']
    db.add_handle(ctx.guild.id, member.id, handle, rating)
    embed = discord.Embed(
        description=f'Handle for {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})',
        color=Color(cf_colors[rank.lower()]))
    embed.add_field(name='Rank', value=f'{rank}', inline=True)
    embed.add_field(name='Rating', value=f'{rating}', inline=True)
    embed.set_thumbnail(url=f"{data['titlePhoto']}")
    await ctx.send(embed=embed)

def has_admin_privilege(ctx):
    if ctx.channel.permissions_for(ctx.author).manage_guild:
        return True
    for role in ['POTD Manager']:
        if role.lower() in [x.name.lower() for x in ctx.author.roles]:
            return True
    return False

@bot.command(name="set_handle", help="Set someone's handle (Admin/Mod/Lockout Manager only)")
async def set_handle(ctx, member: discord.Member=None, handle: str=None):
    if handle is None or member is None:
        await ctx.send('Please specify a user and Codeforces handle.')
        return
    if not has_admin_privilege(ctx):
        await ctx.send(f"{ctx.author.mention} you require 'manage server' permission or the POTD Manager role to use this command")
        return

    data = await cf.check_handle(handle)
    if not data[0]:
        await ctx.send(data[1])
        return

    handle = data[1]['handle']
    if db.get_handle(ctx.guild.id, member.id):
        await ctx.send(f"Handle for user {member.mention} already set to {db.get_handle(ctx.guild.id, member.id)}")
        return
    # 2 discord users setting same handle
    handles = list(filter(lambda x: x[2] == handle, db.get_all_handles(ctx.guild.id)))
    if len(handles):
        await ctx.send('That handle is already in use')
        return

    # all conditions met
    data = data[1]
    if "rating" not in data:
        rating = 0
        rank = "unrated"
    else:
        rating = data['rating']
        rank = data['rank']
    db.add_handle(ctx.guild.id, member.id, handle, rating)
    embed = discord.Embed(
        description=f'Handle for user {member.mention} successfully set to [{handle}](https://codeforces.com/profile/{handle})',
        color=Color(cf_colors[rank.lower()]))
    embed.add_field(name='Rank', value=f'{rank}', inline=True)
    embed.add_field(name='Rating', value=f'{rating}', inline=True)
    embed.set_thumbnail(url=f"{data['titlePhoto']}")
    await ctx.send(embed=embed)

@bot.command(name='get_handle', help='Get your CF handle')
async def get_handle(ctx, member: discord.Member=None):
    if member is None:
        member = ctx.author
    if not db.get_handle(ctx.guild.id, member.id):
        await ctx.send(f'Handle for {member.mention} is not set currently')
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
        rating = data['rating']
        rank = data['rank']
    embed = discord.Embed(
        description=f'Handle for {member.mention} currently set to [{handle}](https://codeforces.com/profile/{handle})',
        color=Color(cf_colors[rank.lower()]))
    embed.add_field(name='Rank', value=f'{rank}', inline=True)
    embed.add_field(name='Rating', value=f'{rating}', inline=True)
    embed.set_thumbnail(url=f"{data['titlePhoto']}")
    await ctx.send(embed=embed)

@bot.command(name="remove_handle", help="Remove someone's handle (Admin/Mod/Lockout Manager only)")
async def remove_handle(ctx, member: discord.Member=None):
    if member is None:
        ctx.send("Please specify a member.")
    if not has_admin_privilege(ctx):
        await ctx.send(f"{ctx.author.mention} you require 'manage server' permission or the POTD Manager role to use this command")
        return
    if not db.get_handle(ctx.guild.id, member.id):
        await ctx.send(f"Handle for {member.mention} not set")
        return

    db.remove_handle(ctx.guild.id, member.id)
    await ctx.send(
        embed=Embed(description=f"Handle for {member.mention} removed successfully", color=Color.green()))

def isNonStandard(contest_name):
    names = [
        'wild', 'fools', 'unrated', 'surprise', 'unknown', 'friday', 'q#', 'testing',
        'marathon', 'kotlin', 'onsite', 'experimental', 'abbyy']
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
        mapping[contest['id']] = contest['name']
        if contest['id'] not in contest_id and contest['phase'] == "FINISHED" and not isNonStandard(contest['name']):
            con_cnt += 1
            db.add_contest(contest['id'], contest['name'])

    for problem in problem_list:
        if problem['contestId'] in mapping and not isNonStandard(mapping[problem['contestId']]) and 'rating' in problem and problem['contestId'] not in problem_id:
            prob_cnt += 1
            db.add_problem(problem['contestId'], problem['index'], problem['name'], problem['type'], problem['rating'], False)

async def find_problem(rating):
    all_problems = db.get_problems()

    problem = None
    options = [p for p in all_problems if p.rating == rating and not p.used]
    weights = [int(p.id * math.sqrt(p.id)) for p in options]
    if options:
        return random.choices(options, weights, k=1)
    if not problem:
        return [False, f"Not enough problems with rating {rating} left!"]

potd_difficulties = [800, 1200, 900, 1300, 1000, 1600, 1400]
async def select_potd():
    diff = potd_difficulties[datetime.today().weekday()]
    problem = (await find_problem(diff))[0]
    db.add_potd(id=problem.id, index=problem.index, name=problem.name)
    db.set_used(id=problem.id, index=problem.index, name=problem.name)
    await bot.get_channel(POTD_PROBLEMS).send("<@&1120846668833771560>", 
        embed=Embed(title="POTD " + datetime.today().strftime('%m/%d/%Y'), description=f"\n[{problem.name}](https://codeforces.com/contest/{problem.id}/problem/{problem.index})", color=Color.blue()))

@bot.command(name="get_potd", help="Get the current POTD")
async def get_potd(ctx):
    problem = db.get_potd()
    await ctx.send(
        embed=Embed(title="POTD " + datetime.today().strftime('%m/%d/%Y'), description=f"\n[{problem.name}](https://codeforces.com/contest/{problem.id}/problem/{problem.index})", color=Color.blue()))

async def check_solved(handle, id, index):
    subs = await cf.get_user_problems(handle, 50)
    if not subs[0]: return False
    for x in subs[1]:
        if x.id == int(id) and x.index == index:
            if x.verdict == 'OK':
                return True
    return False

async def update_solvers():
    problem = db.get_potd()
    if problem is None: return
    users = db.get_all_handles(POTD_GUILD)
    for user in users:
        if await check_solved(user[2], problem.id, problem.index) and not db.check_user_potd(user[2]):
            db.set_user_potd(user[2])
            msg = await bot.get_channel(POTD_ANNOUNCE).send(f"Congratulations to <@{user[1]}> for solving POTD " + datetime.today().strftime('%m/%d/%Y') + "!")
            await msg.add_reaction("<:orz:1105018917828698204>")
    print("Solvers updated")


@bot.command(name="update_potd", help="Update list of POTD solvers")
async def update_potd(ctx):
    await update_solvers()

@bot.command(name="streak_leaderboard", help="Show leaderboard of current streak holders")
async def streak_leaderboard(ctx):
    users = db.get_all_handles()
    user_lb = []
    for user in users:
        streak = 0
        for i in range(len(user) - 1, 3, -1):
            if not user[i]: break
            streak += 1
        user_lb.append([streak, user[2]])
    user_lb.sort()
    user_lb.reverse()
    curr_place = 1
    lb_strings = []
    for i in range(len(user_lb)):
        if (i == 0 or user_lb[i - 1][0] != user_lb[i][0]):
            curr_place = i + 1
        lb_strings.append(str(curr_place) + "\U0000200D. " + user_lb[i][1] + " - " + str(user_lb[i][0]) + " day" + ("s" if user_lb[i][0] != 1 else ""))
    await ctx.send(embed=Embed(title="Current Streak Leaderboard", description='\n'.join(lb_strings), color=Color.orange()))

@bot.command(name="solves_leaderboard", help="Show leaderboard of problems solved")
async def solves_leaderboard(ctx):
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
        if (i == 0 or user_lb[i - 1][0] != user_lb[i][0]):
            curr_place = i + 1
        lb_strings.append(str(curr_place) + "\U0000200D. " + user_lb[i][1] + " - " + str(user_lb[i][0]) + " problem" + ("s" if user_lb[i][0] != 1 else ""))
    await ctx.send(embed=Embed(title="Current Solves Leaderboard", description='\n'.join(lb_strings), color=Color.purple()))

bot.run(TOKEN)