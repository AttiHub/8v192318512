import discord
from discord.ext import commands
import random
import asyncio
import Database
from Database import init_db
import datetime
import aiomysql
import JobFunctions
from Database import init_db_fin
from fuzzywuzzy import process
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import requests
from io import BytesIO
import io



DB_NAME = "MYSQL needed"
DB_HOST = "MYSQL needed"
DB_USER = "MYSQL needed"
DB_PASS = "MYSQL needed"

cogs = ["cogs.roles", "cogs.users", "cogs.moderation", "cogs.ticket-es", "cogs.ticket-en"]
intents = discord.Intents.default()
intents.members = True
intents.messages = True
bot = commands.Bot(command_prefix="$", intents = discord.Intents.all())

pool = None
conn = None

@bot.event
async def on_connect():
    global pool
    global conn
    pool = await aiomysql.create_pool(host=DB_HOST, port=25060,
                                      user=DB_USER, password=DB_PASS,
                                      db=DB_NAME, autocommit=True)
    conn = await pool.acquire()
    await init_db_fin()

    print('Bot {0.user} is running correctly'.format(bot))
    print("-----------------------------------------")
    print("ID: " + str(bot.user.id))
    print("Discord Version: " + str(discord.__version__))
    print(f'Currently in {len(bot.guilds)} servers!')
    for server in bot.guilds:
        print(server.name)
    print("-----------------------------------------")

    # Load cogs
    print("Loading cogs . . .")
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(cog + " has been loaded.")
        except Exception as e:
            print(e)

    print("\n")

    try:
        synced = await bot.tree.sync()
        print(f"synced {len(synced)} command(s)")
    except Exception as e:
        print(e)




MAX_QUEST_ROLLS = 3
MAX_ROLLS = 5
ROLLED_EMOJI = "🎴"
testing = datetime.timedelta(seconds=1)
one_hour = datetime.timedelta(hours=1)
two_hour = datetime.timedelta(hours=2)
four_hour = datetime.timedelta(hours=4)
six_hour = datetime.timedelta(hours=6)
twelve_hour = datetime.timedelta(hours=12)
oneday = datetime.timedelta(hours=24)
threeday_hour = datetime.timedelta(hours=76)
COOLDOWNS = {
    'roll': testing,
    'collect': testing,
    'steal': testing,
    'kidnap': testing,
    'roll_quest': testing,
    'roll_shop': testing,
    'assassinate': testing,
    'pillage': testing,
    'sue': testing,
    'roll_quests': testing,
    'work': testing
}
user_claim_locks = {}

RARITY_WEIGHTS_0 = {
    "Common": 95,
    "Rare": 5,
    "Epic": 0,
}
RARITY_WEIGHTS_1 = {
    "Common": 85,
    "Rare": 10,
    "Epic": 5,
}
RARITY_WEIGHTS_2 = {
    "Common": 73,
    "Rare": 12.75,
    "Epic": 4,
}
RARITY_WEIGHTS_3 = {
    "Common": 73,
    "Rare": 12.75,
    "Epic": 4,
}


LUCK_MULTIPLIER = {
    "Common": 0.85,
    "Rare": 0.65,
    "Epic": 0.50,
}
user_roll_locks = {}  # Initialize this at global scope
@bot.command(name='roll')
async def roll_card(ctx):
    guild_idz = 1104234202624426038
    emoji_coin = 1106589718730264736
    emoji_cardback = 1106596455067693097
    guildz = bot.get_guild(guild_idz)
    coinz = discord.utils.get(guildz.emojis, id=emoji_coin)
    cardbackz = discord.utils.get(guildz.emojis, id=emoji_cardback)

    has_aya_chosen_role = False

    user_id = ctx.author.id
    server_id = ctx.guild.id

    user_roll_lock = user_roll_locks.get(user_id)
    if user_roll_lock is None:
        user_roll_lock = asyncio.Lock()
        user_roll_locks[user_id] = user_roll_lock

    async with user_roll_lock:
        roll_type = random.choices(["card", "spell"], weights=[80, 20], k=1)[0]

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT * FROM player_races WHERE player_id = %s AND server_id = %s
                """, (user_id, server_id))
                alliance_result = await cursor.fetchone()

                # Alliance races - adjust these fields according to your database structure
                allied_races = []
                if alliance_result is not None and alliance_result[12] == 1:
                    allied_races = [race for idx, race in
                                    enumerate(["gnome", "human", "orc", "goblin", "dwarf", "elf"], 4)
                                    if alliance_result[idx]]
                else:
                    await ctx.send("You haven't progressed far enough in the tutorial. Please run"
                                   " \n\n ***$start***\n or\n ***$continue*** \n\n "
                                   "to finish.")
                    return

                await cursor.execute("""
                    SELECT pb.player_id, pb.server_id, MAX(b.tier) 
                    FROM player_buildings pb
                    INNER JOIN buildings b ON pb.building_id = b.id
                    WHERE pb.player_id = %s AND pb.server_id = %s AND b.type = 'tavern'
                    GROUP BY pb.player_id, pb.server_id
                """, (user_id, server_id))
                max_tavern_tier = await cursor.fetchone()
                max_rolls = MAX_ROLLS

                if max_tavern_tier is None:
                    max_tavern_tier = [None, None, 0]  # This line sets the tier to 0 if there is no entry for the user.


                if max_tavern_tier[2] is not None:
                    max_rolls += max_tavern_tier[2]

                can_roll, remaining_time = await Database.can_perform_action(user_id, server_id, 'roll',
                                                                              pool, conn)

                if not can_roll:
                    await ctx.send(
                        f"You've already rolled {max_rolls} times! Please wait {remaining_time} before rolling again.")
                    return

                card_type = random.choices(["Normal", "Special"], weights=[100, 0], k=1)[0]

                if card_type == "Normal":
                    rarity_weights = RARITY_WEIGHTS_0
                    if max_tavern_tier[2] is not None:
                        if max_tavern_tier[2] == 1:
                            rarity_weights = RARITY_WEIGHTS_1
                        elif max_tavern_tier[2] == 2:
                            rarity_weights = RARITY_WEIGHTS_2
                        elif max_tavern_tier[2] == 3:
                            rarity_weights = RARITY_WEIGHTS_3

                    rarity = random.choices(list(rarity_weights.keys()),
                                            weights=list(rarity_weights.values()),
                                            k=1)[0]

                    query = """
                        SELECT * FROM cards WHERE rarity = %s AND race IN ({})
                    """.format(', '.join(['%s' for _ in allied_races]))
                else:
                    print('special huh?')

                await cursor.execute(query, (rarity, *allied_races))
                result = await cursor.fetchall()

                if not result:
                    await ctx.send("No cards available of the rolled rarity!")
                    return

                card = random.choice(result)

                user_claim_lock = user_claim_locks.get(user_id)
                if user_claim_lock is None:
                    user_claim_lock = asyncio.Lock()
                    user_claim_locks[user_id] = user_claim_lock

                async with user_claim_lock:
                    can_claim = True
                    if can_claim:
                        success = await Database.claim_card(server_id, user_id, card[0])
                        if success:
                            # Fetch the newly added card
                            player_card = await Database.get_most_recent_player_card(user_id, server_id)
                            if player_card is not None:
                                # Generate card embed with stats
                                embed = discord.Embed(title=player_card[4],
                                                      description=f'{card[1]} {card[2]} {card[3]}')
                                embed.set_image(url=player_card[5])
                                footer_text = f'Str {player_card[6]} | Int {player_card[7]} | Agi {player_card[8]} | Con {player_card[9]}'
                                embed.set_footer(text=footer_text)
                                await ctx.send(embed=embed)

                            await ctx.send(f' {cardbackz} {player_card[4]} has been added to your deck')
                            await Database.update_action_timestamp(user_id, server_id, 'roll', has_aya_chosen_role)

                        else:
                            await ctx.send('Failed to claim the card.')



#check Claims
@bot.command(name="cards", description="Check your owned cards on the server", brief='See your cards')
async def _owned_cards(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await Database.check_owned_cards(ctx, server_id, player_id, bot, pool)
@bot.command(name="inv", description="Check your owned items on the server", brief='See your inventory')
async def _inventory(ctx):
    server_id = ctx.guild.id
    user_id = ctx.author.id

    await Database.check_owned_items(ctx, server_id, user_id, bot, pool)






#Jobs
class CraftedItemsSelectionView(discord.ui.View):
    def __init__(self, ctx, crafted_categories):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.crafted_categories = crafted_categories
        self.current_category = list(self.crafted_categories.keys())[0]

    async def generate_embed(self):
        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        for subcategory, crafted_items in self.crafted_categories[self.current_category].items():
            description = "\n".join([f"{item_name}: {quantity}" for item_name, quantity in crafted_items.items()])
            embed.add_field(name=subcategory, value=description, inline=True)

        return embed

    @discord.ui.button(label="🍲", style=discord.ButtonStyle.secondary)
    async def food_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Food Items'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="⚕️", style=discord.ButtonStyle.secondary)
    async def healing_potion_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Healing Potions'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="⚔️", style=discord.ButtonStyle.secondary)
    async def weapon_oil_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Weapon Oils'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🛡️", style=discord.ButtonStyle.secondary)
    async def armor_plating_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Armor Plating'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🔒", style=discord.ButtonStyle.secondary)
    async def thief_items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Thief Items'
        await interaction.response.edit_message(embed=await self.generate_embed())
async def check_crafted_items(ctx, server_id, player_id, bot, pool):
    food_items = {
        'Sprigs_Sip': 0,
        'Mead_of_Mending': 0,
        'Elixir_of_Restoration': 0,
        'Nectar_of_Renewal': 0,
        'Ambrosia_of_Life': 0,
        'Panacea_of_Divinity': 0,
        'Wayfarer_Bread': 0,
        'Dwarf_Delight': 0,
        'Heroes_Feast': 0,
        'Gourmets_Grace': 0,
        'Elysian_Meal': 0,
        'Warders_Whisper': 0
    }
    healing_potions = {
        'wolfs_howl': 0,
        'Firebrand': 0,
        'Frostbite': 0,
        'Dragons_Breath': 0,
        'Celestial_Brilliance': 0
    }
    weapon_oils = {
        'Pads': 0,
        'Ironclad': 0,
        'Steel_Bastion': 0,
        'Mithril_Ward': 0,
        'Celestial_Mantle': 0
    }
    armor_plating = {
        'Ambrosia_of_Life': 0,
        'Panacea_of_Divinity': 0,
        'Nectar_of_Renewal': 0,
        'Elixir_of_Restoration': 0,
        'Mead_of_Mending': 0
    }
    thief_items = {
        'Heart_Of_Courage': 0,
        'Titan_Heart': 0,
        'Eternal_Guardian': 0,
        'Immortal_Protector': 0,
        'Empyreal_Savior': 0
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT *
                FROM player_crafted_items
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))

            crafted_items = await cursor.fetchone()

            if not crafted_items:
                await ctx.send("You haven't crafted any items on this server.")
                return []

            column_names = [column[0] for column in cursor.description]
            crafted_items = dict(zip(column_names, crafted_items))

            crafted_categories = {
                'Food Items': {k: v for k, v in crafted_items.items() if k in food_items.keys()},
                'Healing Potions': {k: v for k, v in crafted_items.items() if k in healing_potions.keys()},
                'Weapon Oils': {k: v for k, v in crafted_items.items() if k in weapon_oils.keys()},
                'Armor Plating': {k: v for k, v in crafted_items.items() if k in armor_plating.keys()},
                'Thief Items': {k: v for k, v in crafted_items.items() if k in thief_items.keys()},
            }

            view = CraftedItemsSelectionView(ctx, crafted_categories)
            await ctx.send(embed=await view.generate_embed(), view=view)
@bot.command(name="items", brief='Check your resources')
async def itemss(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id
    await check_crafted_items(ctx, server_id, player_id, bot, pool)
class ResourceSelectionView(discord.ui.View):
    def __init__(self, ctx, resource_categories):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.resource_categories = resource_categories
        self.current_category = list(self.resource_categories.keys())[0]

    async def generate_embed(self):
        embed = discord.Embed(
            color=discord.Color.blurple()
        )

        for subcategory, resources in self.resource_categories[self.current_category].items():
            # Generate the description for each subcategory
            description = "\n".join([f"{resource_name}: {quantity}" for resource_name, quantity in resources.items()])

            # Add this description to the embed
            embed.add_field(name=subcategory, value=description, inline=True)

        return embed

    @discord.ui.button(label="⛏️", style=discord.ButtonStyle.secondary)
    async def mine_gem_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Mine/Gem'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🌲", style=discord.ButtonStyle.secondary)
    async def log_plant_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Log/Plant'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🌾", style=discord.ButtonStyle.secondary)
    async def crop_hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Crop/Hide'
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="📜", style=discord.ButtonStyle.secondary)
    async def parchment_relic_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = 'Parchment/Relic'
        await interaction.response.edit_message(embed=await self.generate_embed())
async def check_owned_resources(ctx, server_id, player_id, bot, pool):
    miner_resources = {
        'Iron_ore': [1, 5, 100],
        'Silver_ore': [1, 5, 40],
        'Gold_ore': [1, 5, 8],
        'Titanium_ore': [1, 5, 4],
        'Mithril_ore': [1, 5, 0.5],
    }
    gems_resources = {
        'Topaz': [1, 3, 25],
        'Sapphire': [1, 3, 15],
        'Ruby': [1, 3, 2],
        'Diamond': [1, 3, 1],
        'Primordial_Onyx': [1, 3, 0.5],
    }
    woodsmen_resources = {
        'Oak_logs': [1, 5, 100],
        'Maple_logs': [1, 5, 40],
        'Yew_logs': [1, 5, 8],
        'BlackAsh_logs': [1, 5, 4],
        'Celestial_logs': [1, 5, 0.5],
    }
    herbs_resources = {
        'Mushrooms': [1, 3, 25],
        'Elf_Thistle': [1, 3, 15],
        'Ember_Root': [1, 3, 2],
        'Shadow_Moss': [1, 3, 1],
        'Mithril_Weed': [1, 3, 0.5],
    }
    farmer_resources = {
        'Cotton': [1, 5, 100],
        'Flax': [1, 5, 40],
        'FireBloom': [1, 5, 8],
        'Runeleaf': [1, 5, 4],
        'Spellweave_Fiber': [1, 5, 0.5],
    }
    skins_resources = {
        'Hide': [1, 3, 25],
        'Silk': [1, 3, 15],
        'Shadow_Pelt': [1, 3, 2],
        'Wyrmwing_Scales': [1, 3, 1],
        'Dragon_Scales': [1, 3, 0.5],
    }
    archaeologist_resources = {
        'Tattered_Parchment': [1, 5, 100],
        'Faded_Parchment': [1, 5, 40],
        'Moonlit_Parchment': [1, 5, 8],
        'Abyssal_Parchment': [1, 5, 4],
        'Celestial_Parchment': [1, 5, 0.5],
    }
    relics_resources = {
        'Faded_shard': [1, 3, 25],
        'Emblem': [1, 3, 15],
        'Crimson_Orb': [1, 3, 2],
        'Mythril_Amulet': [1, 3, 1],
        'Divine_Relic': [1, 3, 0.5],
    }

    display_names = {
        'Iron_ore': 'Iron',
        'Silver_ore': 'Silver',
        'Gold_ore': 'Gold',
        'Titanium_ore': 'Titanium',
        'Mithril_ore': 'Mithril',
        'Topaz': 'Topaz',
        'Sapphire': 'Sapphire',
        'Ruby': 'Ruby',
        'Diamond': 'Diamond',
        'Primordial_Onyx': 'Onyx',
        'Oak_logs': 'Oak',
        'Maple_logs': 'Maple',
        'Yew_logs': 'Yew',
        'BlackAsh_logs': 'Black Ash',
        'Celestial_logs': 'Celestial',
        'Mushrooms': 'Mushrooms',
        'Elf_Thistle': 'Elf Thistle',
        'Ember_Root': 'Ember Root',
        'Shadow_Moss': 'Shadow Moss',
        'Mithril_Weed': 'Mithril Weed',
        'Cotton': 'Cotton',
        'Flax': 'Flax',
        'FireBloom': 'FireBloom',
        'Runeleaf': 'Runeleaf',
        'Spellweave_Fiber': 'Spellweave',
        'Hide': 'Hide',
        'Silk': 'Silk',
        'Shadow_Pelt': 'Shadow',
        'Wyrmwing_Scales': 'Wyrmwing',
        'Dragon_Scales': 'Dragon',
        'Tattered_Parchment': 'Tattered',
        'Faded_Parchment': 'Faded',
        'Moonlit_Parchment': 'Moonlit',
        'Abyssal_Parchment': 'Abyssal',
        'Celestial_Parchment': 'Celestial',
        'Faded_shard': 'Faded',
        'Emblem': 'Emblem',
        'Crimson_Orb': 'Crimson',
        'Mythril_Amulet': 'Mythril',
        'Divine_Relic': 'Divine'
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT *
                FROM player_resources
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))

            resources = await cursor.fetchone()

            if not resources:
                await ctx.send("You don't own any resources on this server.")
                return []

            # Get the column names from the cursor description
            column_names = [column[0] for column in cursor.description]

            # Convert tuples to dictionaries
            resources = dict(zip(column_names, resources))


            resource_categories = {
                'Mine/Gem': {
                    'Ores': {display_names.get(k, k): v for k, v in resources.items() if k in miner_resources.keys()},
                    'Gems': {display_names.get(k, k): v for k, v in resources.items() if k in gems_resources.keys()},
                },
                'Log/Plant': {
                    'Logs': {display_names.get(k, k): v for k, v in resources.items() if
                             k in woodsmen_resources.keys()},
                    'Plants': {display_names.get(k, k): v for k, v in resources.items() if k in herbs_resources.keys()},
                },
                'Crop/Hide': {
                    'Crops': {display_names.get(k, k): v for k, v in resources.items() if k in farmer_resources.keys()},
                    'Hides': {display_names.get(k, k): v for k, v in resources.items() if k in skins_resources.keys()},
                },
                'Parchment/Relic': {
                    'Parchments': {display_names.get(k, k): v for k, v in resources.items() if
                                   k in archaeologist_resources.keys()},
                    'Relics': {display_names.get(k, k): v for k, v in resources.items() if
                               k in relics_resources.keys()},
                }
            }


            view = ResourceSelectionView(ctx, resource_categories)
            await ctx.send(embed=await view.generate_embed(), view=view)

@bot.command(name="work", description="Go to work", brief='Work to earn resources')
async def work(ctx):
    bot = ctx.bot
    guild_idz = 1104234202624426038
    server_id = ctx.guild.id
    player_id = ctx.author.id
    guildz = bot.get_guild(guild_idz)
    conn = None

    can_roll, remaining_time = await Database.can_perform_action(player_id, server_id, 'work',
                                                                 pool, conn)
    if not can_roll:
        await ctx.send(
            f"You're too tired! Please waitt {remaining_time}")
        return



    emojis = {
        'Iron_ore': "🪨",
        'Silver_ore': "🪨",
        'Gold_ore': "🪨",
        'Titanium_ore': "🪨",
        'Mithril_ore': "🪨",
        'Topaz': "💎",
        'Sapphire': "💎",
        'Ruby': "💎",
        'Diamond': "💎",
        'Primordial_Onyx': "💎",
        'Oak_logs': "🪵",
        'Maple_logs': "🪵",
        'Yew_logs': "🪵",
        'BlackAsh_logs': "🪵",
        'Celestial_logs': "🪵",
        'Mushrooms': " 🌿 ",
        'Elf_Thistle': " 🌿 ",
        'Ember_Root': " 🌿 ",
        'Shadow_Moss': " 🌿 ",
        'Mithril_Weed': " 🌿 ",
        'Cotton': "🧵",
        'Flax': "🧵",
        'FireBloom': "🧵",
        'Runeleaf': "🧵",
        'Spellweave_Fiber': "🧵",
        'Hide': "🦴",
        'Silk': "🦴",
        'Shadow_Pelt': "🦴",
        'Wyrmwing_Scales': "🦴",
        'Dragon_Scales': "🦴",
        'Tattered_Parchment': "📜",
        'Faded_Parchment': "📜",
        'Moonlit_Parchment': "📜",
        'Abyssal_Parchment': "📜",
        'Celestial_Parchment': "📜",
        'Faded_shard': "📿",
        'Emblem': "📿",
        'Crimson_Orb': "📿",
        'Mythril_Amulet': "📿",
        'Divine_Relic': "📿"
    }


    # define resources miners can collect
    miner_resources = {
        'Iron_ore': [1, 5, 100],
        'Silver_ore': [1, 5, 15],
        'Gold_ore': [1, 5, 3.5],
        'Titanium_ore': [1, 5, 1],
        'Mithril_ore': [1, 5, 0.2],
    }
    gems_resources = {
        'Topaz': [1, 3, 15],
        'Sapphire': [1, 3, 5],
        'Ruby': [1, 3, 0.5],
        'Diamond': [1, 3, 0.25],
        'Primordial_Onyx': [1, 3, 0.1],
    }
    woodsmen_resources = {
        'Oak_logs': [1, 5, 100],
        'Maple_logs': [1, 5, 15],
        'Yew_logs': [1, 5, 3.5],
        'BlackAsh_logs': [1, 5, 1],
        'Celestial_logs': [1, 5, 0.2],
    }
    herbs_resources = {
        'Mushrooms': [1, 3, 15],
        'Elf_Thistle': [1, 3, 5],
        'Ember_Root': [1, 3, 0.5],
        'Shadow_Moss': [1, 3, 0.25],
        'Mithril_Weed': [1, 3, 0.1],
    }
    farmer_resources = {
        'Cotton': [1, 5, 100],
        'Flax': [1, 5, 15],
        'FireBloom': [1, 5, 3.5],
        'Runeleaf': [1, 5, 1],
        'Spellweave_Fiber': [1, 5, 0.1],
    }
    skins_resources = {
        'Hide': [1, 3, 15],
        'Silk': [1, 3, 5],
        'Shadow_Pelt': [1, 3, 0.5],
        'Wyrmwing_Scales': [1, 3, 0.25],
        'Dragon_Scales': [1, 3, 0.1],
    }
    archaeologist_resources = {
        'Tattered_Parchment': [1, 5, 100],
        'Faded_Parchment': [1, 5, 15],
        'Moonlit_Parchment': [1, 5, 3.5],
        'Abyssal_Parchment': [1, 5, 1],
        'Celestial_Parchment': [1, 5, 0.2],
    }
    relics_resources = {
        'Faded_shard': [1, 3, 15],
        'Emblem': [1, 3, 5],
        'Crimson_Orb': [1, 3, 0.5],
        'Mythril_Amulet': [1, 3, 0.25],
        'Divine_Relic': [1, 3, 0.1],
    }
    resources_collected = {resource: 0 for resource in {**miner_resources, **gems_resources}.keys()}

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT job_name, Proficiency, Stamina, Focus FROM player_jobs WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is None:
                await ctx.send("You don't have a job yet. Select a job first.")
                return

            job_name, proficiency, stamina, focus = data
            if job_name == "Miner":
                resources_collected = {resource: 0 for resource in {**miner_resources, **gems_resources}.keys()}
                main_resources, secondary_resources = miner_resources, gems_resources
            elif job_name == "Woodsman":
                resources_collected = {resource: 0 for resource in {**woodsmen_resources, **herbs_resources}.keys()}
                main_resources, secondary_resources = woodsmen_resources, herbs_resources
            elif job_name == "Farmer":
                resources_collected = {resource: 0 for resource in {**farmer_resources, **skins_resources}.keys()}
                main_resources, secondary_resources = farmer_resources, skins_resources
            elif job_name == "Archaeologist":
                resources_collected = {resource: 0 for resource in {**archaeologist_resources, **relics_resources}.keys()}
                main_resources, secondary_resources = archaeologist_resources, relics_resources
            else:
                await ctx.send("Invalid job. Only Miners and Woodsmen can gather resources.")
                return

            # Check if the player has an entry in the player_resources table
            await cur.execute("""
                SELECT player_id FROM player_resources WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is None:
                # Create an entry if not present
                await cur.execute("""
                    INSERT INTO player_resources (player_id, server_id) VALUES (%s, %s)
                """, (ctx.author.id, ctx.guild.id))

            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT MAX(buildings.tier)
                    FROM player_buildings 
                    INNER JOIN buildings ON player_buildings.building_id = buildings.id 
                    WHERE server_id = %s AND player_id = %s AND buildings.type = 'tavern' AND player_buildings.destroyed = 0
                """, (int(server_id), int(player_id)))
                result = await cursor.fetchone()

                gathering_tier = 0
                if result is not None and result[0] is not None:
                    gathering_tier, = result
                # Boost focus, stamina, and proficiency
                focus += gathering_tier * 5
                stamina += gathering_tier * 5
                proficiency += gathering_tier * 5

            # Generate resources based on Proficiency, Stamina and Focus
            for resource, (min_range, max_range, chance) in {**main_resources, **secondary_resources}.items():
                if random.random() < min((chance + chance * focus / 5),
                                         100) / 100:  # chance increases with focus percentage
                    base_amount = random.randint(min_range, max_range)
                    amount = base_amount + base_amount * stamina * proficiency / 100
                    amount = max(1, amount)
                    resources_collected[resource] += int(amount)
                    await cur.execute(f"""
                            UPDATE player_resources
                            SET {resource} = {resource} + %s
                            WHERE player_id = %s AND server_id = %s
                        """, (int(amount), player_id, server_id))
            await Database.update_action_timestamp(player_id, server_id, 'work', False)
            await conn.commit()
    resources_text = "\n".join(
        [f"{resource}: {amount}" for resource, amount in resources_collected.items() if amount > 0])
    embed = discord.Embed(title="You've Gathered:", color=discord.Color.green())
    for resource, amount in resources_collected.items():
        if amount > 0:
            emoji = emojis.get(resource, "")
            resource_name = resource.replace("_", " ").title()
            embed.add_field(name=f"{emoji} {resource_name}", value=amount, inline=True)
    await ctx.send(embed=embed)
@bot.command(name="resources", brief='Check your resources')
async def resources(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id
    await check_owned_resources(ctx, server_id, player_id, bot, pool)



#Shopping
resource_names = [
    "Oak_logs", "Maple_logs", "Yew_logs", "BlackAsh_logs", "Celestial_logs",
    "Mushrooms", "Elf_Thistle", "Ember_Root", "Shadow_Moss", "Mithril_Weed",
    "Iron_ore", "Silver_ore", "Gold_ore", "Titanium_ore", "Mithril_ore",
    "Topaz", "Sapphire", "Ruby", "Diamond", "Primordial_Onyx",
    "Cotton", "Flax", "FireBloom", "Runeleaf", "Spellweave_Fiber",
    "Hide", "Silk", "Shadow_Pelt", "Wyrmwing_Scales", "Dragon_Scales",
    "Tattered_Parchment", "Faded_Parchment", "Moonlit_Parchment", "Abyssal_Parchment", "Celestial_Parchment",
    "Faded_shard", "Emblem", "Crimson_Orb", "Mythril_Amulet", "Divine_Relic"
]
resource_prices = {
    # logs
    "Oak_logs": (10, 7),
    "Maple_logs": (40, 28),
    "Yew_logs": (120, 84),
    "BlackAsh_logs": (360, 252),
    "Celestial_logs": (1080, 756),

    # herbs
    "Mushrooms": (40, 28),
    "Elf_Thistle": (140, 98),
    "Ember_Root": (420, 294),
    "Shadow_Moss": (1260, 882),
    "Mithril_Weed": (3780, 2646),

    # ores
    "Iron_ore": (10, 7),
    "Silver_ore": (40, 28),
    "Gold_ore": (120, 84),
    "Titanium_ore": (360, 252),
    "Mithril_ore": (1080, 756),

    # gems
    "Topaz": (40, 28),
    "Sapphire": (140, 98),
    "Ruby": (420, 294),
    "Diamond": (1260, 882),
    "Primordial_Onyx": (3780, 2646),

    # crops
    "Cotton": (10, 7),
    "Flax": (40, 28),
    "FireBloom": (120, 84),
    "Runeleaf": (360, 252),
    "Spellweave_Fiber": (1080, 756),

    # hides
    "Hide": (40, 28),
    "Silk": (140, 98),
    "Shadow_Pelt": (420, 294),
    "Wyrmwing_Scales": (1260, 882),
    "Dragon_Scales": (3780, 2646),

    # parchments
    "Tattered_Parchment": (10, 7),
    "Faded_Parchment": (40, 28),
    "Moonlit_Parchment": (120, 84),
    "Abyssal_Parchment": (360, 252),
    "Celestial_Parchment": (1080, 756),

    # artifacts
    "Faded_shard": (40, 28),
    "Emblem": (140, 98),
    "Crimson_Orb": (420, 294),
    "Mythril_Amulet": (1260, 882),
    "Divine_Relic": (3780, 2646),
}
crafted_item_names = [
    "Sprigs_Sip",
    "Mead_of_Mending",
    "Elixir_of_Restoration",
    "Nectar_of_Renewal",
    "Ambrosia_of_Life",
    "Panacea_of_Divinity",
    "Wayfarer_Bread",
    "Dwarf_Delight",
    "Heroes_Feast",
    "Gourmets_Grace",
    "Elysian_Meal",
    "Warders_Whisper",
    "wolfs_howl",
    "Firebrand",
    "Frostbite",
    "Dragons_Breath",
    "Celestial_Brilliance",
    "Pads",
    "Ironclad",
    "Steel_Bastion",
    "Mithril_Ward",
    "Celestial_Mantle",
    "Lockpicks",
    "Slippery_Spheres",
    "Nightwalker_paint",
    "Shadowmantle",
    "Skeleton_Key"
]
crafted_item_prices = {
    # Potions
    "Sprigs_Sip": (150, 70),
    "Mead_of_Mending": (200, 140),
    "Elixir_of_Restoration": (300, 210),
    "Nectar_of_Renewal": (400, 280),
    "Ambrosia_of_Life": (500, 350),
    "Panacea_of_Divinity": (600, 420),

    # Food
    "Wayfarer_Bread": (80, 35),
    "Dwarf_Delight": (100, 70),
    "Heroes_Feast": (150, 105),
    "Gourmets_Grace": (200, 140),
    "Elysian_Meal": (250, 175),

    # Magic items
    "Warders_Whisper": (1000, 700),
    "wolfs_howl": (2000, 1400),
    "Firebrand": (3000, 2100),
    "Frostbite": (4000, 2800),
    "Dragons_Breath": (5000, 3500),
    "Celestial_Brilliance": (6000, 4200),

    # Armors
    "Pads": (500, 350),
    "Ironclad": (1000, 700),
    "Steel_Bastion": (1500, 1050),
    "Mithril_Ward": (2000, 1400),
    "Celestial_Mantle": (2500, 1750),

    # Locks
    "Lockpicks": (50, 35),
    "Slippery_Spheres": (100, 70),
    "Nightwalker_paint": (150, 105),
    "Shadowmantle": (200, 140),
    "Skeleton_Key": (250, 175),
}
class MarketCraftedSelectionView(discord.ui.View):
    crafted_item_categories = {
        "🍵": ["Sprigs_Sip", "Mead_of_Mending", "Elixir_of_Restoration", "Nectar_of_Renewal", "Ambrosia_of_Life", "Panacea_of_Divinity"],
        "🍞": ["Wayfarer_Bread", "Dwarf_Delight", "Heroes_Feast", "Gourmets_Grace", "Elysian_Meal"],
        "⚔️": ["Warders_Whisper", "wolfs_howl", "Firebrand", "Frostbite", "Dragons_Breath", "Celestial_Brilliance"],
        "🛡️": ["Pads", "Ironclad", "Steel_Bastion", "Mithril_Ward", "Celestial_Mantle"],
        "🔐": ["Lockpicks", "Slippery_Spheres", "Nightwalker_paint", "Shadowmantle", "Skeleton_Key"]
    }

    crafted_item_aliases = {
        "Sprigs_Sip": "Sip",
        "Mead_of_Mending": "MoM",
        "Elixir_of_Restoration": "EoR",
        "Nectar_of_Renewal": "NoR",
        "Ambrosia_of_Life": "AoL",
        "Panacea_of_Divinity": "PoD",
        "Wayfarer_Bread": "W. Bread",
        "Dwarf_Delight": "D. Delight",
        "Heroes_Feast": "H. Feast",
        "Gourmets_Grace": "G. Grace",
        "Elysian_Meal": "E. Meal",
        "Warders_Whisper": "W. Whisper",
        "wolfs_howl": "W. Howl",
        "Firebrand": "Fbrand",
        "Frostbite": "Fbite",
        "Dragons_Breath": "D. Breath",
        "Celestial_Brilliance": "C. Brill",
        "Pads": "Pads",
        "Ironclad": "Iclad",
        "Steel_Bastion": "S. Bastion",
        "Mithril_Ward": "M. Ward",
        "Celestial_Mantle": "C. Mantle",
        "Lockpicks": "Lockpick",
        "Slippery_Spheres": "S. Spheres",
        "Nightwalker_paint": "N. Paint",
        "Shadowmantle": "Smantle",
        "Skeleton_Key": "S. Key"
    }

    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.current_category = list(self.crafted_item_categories.keys())[0]

    async def generate_embed(self):
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM server_crafted_items WHERE server_id = %s",
                                     (self.ctx.guild.id,))
                if (await cursor.fetchone())[0] == 0:
                    await cursor.execute(
                        "INSERT INTO server_crafted_items (server_id, Sprigs_Sip, Wayfarer_Bread) VALUES (%s, 999999, 999999)",
                        (self.ctx.guild.id,))

                embed = discord.Embed()
                for i, crafted_item_name in enumerate(self.crafted_item_categories[self.current_category]):
                    await cursor.execute(f"""
                        SELECT {crafted_item_name} 
                        FROM server_crafted_items
                        WHERE server_id = %s
                    """, (self.ctx.guild.id,))
                    crafted_item_quantity_result = await cursor.fetchone()
                    if crafted_item_quantity_result is None:
                        crafted_item_quantity = 0
                    else:
                        crafted_item_quantity = crafted_item_quantity_result[0]

                    if crafted_item_name in ["Sprigs_Sip", "Wayfarer_Bread"]:
                        crafted_item_quantity = '9999+'

                    buy_price, sell_price = get_crafted_item_prices(crafted_item_name)
                    crafted_item_name_display = self.crafted_item_aliases[crafted_item_name]

                    embed.add_field(name=f"{crafted_item_name_display} - {crafted_item_quantity}",
                                    value=f"Buy/Sell: {buy_price}/{sell_price}",
                                    inline=True)
                    if i % 2 == 1:
                        embed.add_field(name="\u200b", value="\u200b", inline=True)
        return embed


    @discord.ui.button(label="🍵", style=discord.ButtonStyle.secondary)
    async def potions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "🍵"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🍞", style=discord.ButtonStyle.secondary)
    async def food_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "🍞"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="⚔️", style=discord.ButtonStyle.secondary)
    async def magic_items_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "⚔️"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🛡️", style=discord.ButtonStyle.secondary)
    async def armors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "🛡️"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🔐", style=discord.ButtonStyle.secondary)
    async def locks_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "🔐"
        await interaction.response.edit_message(embed=await self.generate_embed())
class MarketSelectionView(discord.ui.View):
    resource_categories = {
        "⛏️": ["Iron_ore", "Silver_ore", "Gold_ore", "Titanium_ore", "Mithril_ore", "Topaz", "Sapphire", "Ruby",  "Diamond", "Primordial_Onyx"],
        "🌲": ["Oak_logs", "Maple_logs", "Yew_logs", "BlackAsh_logs", "Celestial_logs", "Mushrooms", "Elf_Thistle", "Ember_Root", "Shadow_Moss", "Mithril_Weed"],
        "🌾": ["Cotton", "Flax", "FireBloom", "Runeleaf", "Spellweave_Fiber", "Hide", "Silk", "Shadow_Pelt", "Wyrmwing_Scales", "Dragon_Scales"],
        "📜": ["Tattered_Parchment", "Faded_Parchment", "Moonlit_Parchment", "Abyssal_Parchment", "Celestial_Parchment", "Faded_shard", "Silk", "Emblem", "Crimson_Orb", "Divine_Relic"]
    }
    resource_names_mapping = {
        "Iron_ore": "Iron",
        "Silver_ore": "Silver",
        "Gold_ore": "Gold",
        "Titanium_ore": "Titanium",
        "Mithril_ore": "Mithril",
        "Topaz": "Topaz",
        "Sapphire": "Sapphire",
        "Ruby": "Ruby",
        "Diamond": "Diamond",
        "Primordial_Onyx": "Onyx",
        "Oak_logs": "Oak",
        "Maple_logs": "Maple",
        "Yew_logs": "Yew",
        "BlackAsh_logs": "Black Ash",
        "Celestial_logs": "Celestial",
        "Mushrooms": "Mushrooms",
        "Elf_Thistle": "Elf Thistle",
        "Ember_Root": "Ember Root",
        "Shadow_Moss": "Shadow Moss",
        "Mithril_Weed": "Mithril Weed",
        "Cotton": "Cotton",
        "Flax": "Flax",
        "FireBloom": "Fire Bloom",
        "Runeleaf": "Runeleaf",
        "Spellweave_Fiber": "Spellweave",
        "Hide": "Hide",
        "Silk": "Silk",
        "Shadow_Pelt": "Shadow Pelt",
        "Wyrmwing_Scales": "Wyrmwing",
        "Dragon_Scales": "Dragon Scales",
        "Tattered_Parchment": "Tattered",
        "Faded_Parchment": "Faded",
        "Moonlit_Parchment": "Moonlit",
        "Abyssal_Parchment": "Abyssal",
        "Celestial_Parchment": "Celestial",
        "Faded_shard": "Faded Shard",
        "Emblem": "Emblem",
        "Crimson_Orb": "Crimson",
        "Divine_Relic": "Divine"
    }
    def __init__(self, ctx):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.current_category = list(self.resource_categories.keys())[0]

    async def generate_embed(self):
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                embed = discord.Embed()
                for i, resource_name in enumerate(self.resource_categories[self.current_category]):
                    await cursor.execute(f"""
                        SELECT {resource_name} 
                        FROM server_resources
                        WHERE server_id = %s
                    """, (self.ctx.guild.id,))
                    resource_quantity_result = await cursor.fetchone()
                    if resource_quantity_result is None:
                        resource_quantity = 0
                    else:
                        resource_quantity = resource_quantity_result[0]
                    buy_price, sell_price = get_resource_prices(resource_name)
                    # Use the new name in the embed.
                    new_resource_name = self.resource_names_mapping.get(resource_name, resource_name)
                    embed.add_field(name=f"{new_resource_name} {resource_quantity}",
                                    value=f"buy/sell {buy_price}/{sell_price}",
                                    inline=True)
                    # After every 2 resources, add an empty field to start a new row
                    if i % 2 == 1:
                        embed.add_field(name="\u200b", value="\u200b", inline=True)
        return embed

    @discord.ui.button(label="⛏️", style=discord.ButtonStyle.secondary)
    async def ores_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "⛏️"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🌲", style=discord.ButtonStyle.secondary)
    async def logs_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "🌲"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="🌾", style=discord.ButtonStyle.secondary)
    async def crops_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "🌾"
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="📜", style=discord.ButtonStyle.secondary)
    async def parchments_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_category = "📜"
        await interaction.response.edit_message(embed=await self.generate_embed())
def get_crafted_item_prices(crafted_item_name):
    return crafted_item_prices[crafted_item_name]
def get_resource_prices(resource_name):
    return resource_prices[resource_name]
@bot.command(name="market", description="View the server's resources")
async def view_server_resources(ctx):
    view = MarketSelectionView(ctx)
    embed = await view.generate_embed()  # default to the first category on load
    await ctx.send(embed=embed, view=view)
@bot.command(name="market2", description="View the server's resources")
async def view_server_resources2(ctx):
    view = MarketCraftedSelectionView(ctx)
    embed = await view.generate_embed()  # default to the first category on load
    await ctx.send(embed=embed, view=view)
@bot.command(name="sell", description="Sell a resource to the server")
async def sell(ctx, resource_name_input: str = None, quantity: int = None):
    if resource_name_input is None or quantity is None:
        await ctx.send("Please provide the resource name and quantity. Example: ***$sell oak 5*** \n\n"
                       "Alternatively just use ***$sellall*** to sell everything")
        return

    server_id = ctx.guild.id
    player_id = ctx.author.id
    resource_name = process.extractOne(resource_name_input, resource_names)[0]
    sell_price = get_resource_prices(resource_name)[1]

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Check if server_id already exists in the server_resources table
            await cursor.execute(f"""
                SELECT 1 FROM server_resources WHERE server_id = %s
            """, (server_id,))
            if not await cursor.fetchone():
                # If server_id does not exist, insert it into the table
                await cursor.execute(f"""
                    INSERT INTO server_resources (server_id, {resource_name})
                    VALUES (%s, 0)
                """, (server_id,))

            # Fetch server quantity
            await cursor.execute(f"""
                SELECT {resource_name} 
                FROM server_resources 
                WHERE server_id = %s
            """, (server_id,))
            server_quantity_result = await cursor.fetchone()
            server_quantity = server_quantity_result[0] if server_quantity_result else 0

            # Fetch player quantity
            await cursor.execute(f"""
                SELECT {resource_name} 
                FROM player_resources
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))
            player_quantity_result = await cursor.fetchone()
            player_quantity = player_quantity_result[0] if player_quantity_result else 0

            if server_quantity is None or player_quantity is None or player_quantity < quantity:
                await ctx.send(f"You do not have enough {resource_name} to sell.")
                return

            total_price = quantity * sell_price

            # Now we can be sure that server_id exists in the table and directly update its corresponding column
            await cursor.execute(f"""
                UPDATE server_resources
                SET {resource_name} = {resource_name} + %s
                WHERE server_id = %s
            """, (quantity, server_id,))

            await cursor.execute(f"""
                UPDATE player_resources
                SET {resource_name} = {resource_name} - %s
                WHERE server_id = %s AND player_id = %s
            """, (quantity, server_id, player_id,))

            total_florins = await Database.give_florins(server_id, player_id, total_price)
            await ctx.send(
                f"You've sold {quantity} {resource_name} for {total_price} florins. You now have {total_florins} florins.")
@bot.command(name="buy", description="Buy a resource from the server")
async def buy(ctx, resource_name_input: str = None, quantity: int = None):
    if resource_name_input is None or quantity is None:
        await ctx.send("Please provide the resource name and quantity. Example: ***$buy oak 5***")
        return
    server_id = ctx.guild.id
    player_id = ctx.author.id
    resource_name = process.extractOne(resource_name_input, resource_names)[0]
    buy_price = get_resource_prices(resource_name)[0]

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(f"""
                SELECT {resource_name} 
                FROM server_resources 
                WHERE server_id = %s
            """, (server_id,))
            server_quantity_result = await cursor.fetchone()
            server_quantity = server_quantity_result[0] if server_quantity_result else None

            await cursor.execute(f"""
                SELECT {resource_name} 
                FROM player_resources
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))
            player_quantity_result = await cursor.fetchone()
            player_quantity = player_quantity_result[0] if player_quantity_result else None

            if server_quantity is None or player_quantity is None or server_quantity < quantity:
                await ctx.send(f"The server does not have enough {resource_name} to sell.")
                return

            total_price = quantity * buy_price

            await cursor.execute(f"""
                UPDATE server_resources
                SET {resource_name} = {resource_name} - %s
                WHERE server_id = %s
            """, (quantity, server_id,))

            await cursor.execute(f"""
                UPDATE player_resources
                SET {resource_name} = {resource_name} + %s
                WHERE server_id = %s AND player_id = %s
            """, (quantity, server_id, player_id,))

            total_florins = await Database.deduct_florins(server_id, player_id, total_price)
            await ctx.send(f"You've bought {quantity} {resource_name} for {total_price} florins. You now have {total_florins} florins.")
@bot.command(name="sellall", description="Sell all resources to the server")
async def sell_all(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Fetch player resources and quantities in one go
            await cursor.execute(f"""
                SELECT *
                FROM player_resources
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))
            player_resources = await cursor.fetchone()

            if player_resources is None:
                await ctx.send("You have no resources to sell.")
                return

            # Get column names
            column_names = [desc[0] for desc in cursor.description]

            # Form a dictionary mapping column names to values
            player_resources_dict = dict(zip(column_names, player_resources))

            # Check if server resource record exists
            await cursor.execute(f"""
                SELECT 1
                FROM server_resources
                WHERE server_id = %s
            """, (server_id,))
            record_exists = await cursor.fetchone()

            # If no record exists for server, create one
            if not record_exists:
                await cursor.execute(f"""
                    INSERT INTO server_resources(server_id)
                    VALUES (%s)
                """, (server_id,))

            total_earned = 0

            # Initialize empty strings for queries
            update_server_query = ""
            update_player_query = ""
            params_server = []
            non_resource_columns = ['player_res_id', 'server_id', 'player_id', 'job_level', 'remaining_stat_points', 'Stamina', 'Focus', 'Proficiency']

            for resource_name, player_quantity in player_resources_dict.items():
                # Skip if quantity is zero or column name is not an actual resource
                if player_quantity <= 0 or resource_name in non_resource_columns:
                    continue

                sell_price = get_resource_prices(resource_name)[1]
                total_earned += player_quantity * sell_price

                # If the player has resources, construct the SQL queries
                if update_server_query == "":
                    update_server_query = "UPDATE server_resources SET "
                    update_player_query = "UPDATE player_resources SET "

                update_server_query += f"{resource_name} = {resource_name} + %s, "
                update_player_query += f"{resource_name} = 0, "
                params_server.append(player_quantity)

            # Check if there were any resources to sell. If not, inform the player and return
            if update_server_query == "":
                await ctx.send("You have no resources to sell.")
                return

            # Continue with your previous code
            update_server_query = update_server_query.rstrip(', ') + f" WHERE server_id = %s"
            params_server.append(server_id)
            await cursor.execute(update_server_query, params_server)

            update_player_query = update_player_query.rstrip(', ') + f" WHERE server_id = %s AND player_id = %s"
            params_player = [server_id, player_id]
            await cursor.execute(update_player_query, params_player)

            total_florins = await Database.give_florins(server_id, player_id, total_earned)
            await ctx.send(f"You've sold all your resources for {total_earned} florins. You now have {total_florins} florins.")
@bot.command(name="sell2", description="Sell a crafted item to the server")
async def sell(ctx, item_name_input: str = None, quantity: int = None):
    if item_name_input is None or quantity is None:
        await ctx.send("Please provide the item name and quantity. Example: ***$sell Sprigs_Sip 5*** \n\n"
                       "Alternatively just use ***$sellall*** to sell everything")
        return

    server_id = ctx.guild.id
    player_id = ctx.author.id
    item_name = process.extractOne(item_name_input, crafted_item_names)[0]
    sell_price = get_crafted_item_prices(item_name)[1]

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(f"""
                SELECT {item_name} 
                FROM server_crafted_items
                WHERE server_id = %s
            """, (server_id,))
            server_quantity_result = await cursor.fetchone()
            server_quantity = server_quantity_result[0] if server_quantity_result else 0

            await cursor.execute(f"""
                SELECT {item_name} 
                FROM player_crafted_items
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))
            player_quantity_result = await cursor.fetchone()
            player_quantity = player_quantity_result[0] if player_quantity_result else 0

            if server_quantity is None or player_quantity is None or player_quantity < quantity:
                await ctx.send(f"You do not have enough {item_name} to sell.")
                return

            total_price = quantity * sell_price

            await cursor.execute(f"""
                UPDATE server_crafted_items
                SET {item_name} = {item_name} + %s
                WHERE server_id = %s
            """, (quantity, server_id,))

            await cursor.execute(f"""
                UPDATE player_crafted_items
                SET {item_name} = {item_name} - %s
                WHERE server_id = %s AND player_id = %s
            """, (quantity, server_id, player_id,))
            await Database.give_florins(server_id, player_id, total_price)
            total_florins = await Database.get_florins(server_id, player_id)
            await ctx.send(
                f"You've sold {quantity} {item_name} for {total_price} florins. You now have {total_florins} florins.")
@bot.command(name="buy2", description="Buy a crafted item from the server")
async def buy(ctx, item_name_input: str = None, quantity: int = None):
    if item_name_input is None or quantity is None:
        await ctx.send("Please provide the item name and quantity. Example: ***$buy Sprigs_Sip 5***")
        return

    server_id = ctx.guild.id
    player_id = ctx.author.id
    item_name = process.extractOne(item_name_input, crafted_item_names)[0]
    buy_price = get_crafted_item_prices(item_name)[0]

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(f"""
                SELECT {item_name} 
                FROM server_crafted_items 
                WHERE server_id = %s
            """, (server_id,))
            server_quantity_result = await cursor.fetchone()
            server_quantity = server_quantity_result[0] if server_quantity_result else None

            if server_quantity is None or server_quantity < quantity:
                await ctx.send(f"The server does not have enough {item_name} to sell.")
                return

            total_price = quantity * buy_price

            await cursor.execute(f"""
                UPDATE server_crafted_items
                SET {item_name} = {item_name} - %s
                WHERE server_id = %s
            """, (quantity, server_id,))

            await cursor.execute(f"""
                UPDATE player_crafted_items
                SET {item_name} = {item_name} + %s
                WHERE server_id = %s AND player_id = %s
            """, (quantity, server_id, player_id,))

            total_florins = await Database.get_florins(server_id, player_id)

            if total_florins < total_price:
                await ctx.send("hol up")
                return
            await Database.deduct_florins(server_id, player_id, total_price)
            await ctx.send(
                f"You've bought {quantity} {item_name} for {total_price} florins. You now have {total_florins} florins.")
@bot.command(name="sellall2", description="Sell all crafted items to the server")
async def sell_all(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(f"""
                SELECT *
                FROM player_crafted_items
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))
            player_items = await cursor.fetchone()

            if player_items is None:
                await ctx.send("You have no items to sell.")
                return

            column_names = [desc[0] for desc in cursor.description]
            player_items_dict = dict(zip(column_names, player_items))

            total_earned = 0
            update_server_query = ""
            update_player_query = ""
            params_server = []

            for item_name, player_quantity in player_items_dict.items():
                if player_quantity <= 0 or item_name in ['player_res_id', 'server_id', 'player_id']:
                    continue

                sell_price = get_crafted_item_prices(item_name)[1]
                total_earned += player_quantity * sell_price

                if update_server_query == "":
                    update_server_query = "UPDATE server_crafted_items SET "
                    update_player_query = "UPDATE player_crafted_items SET "

                update_server_query += f"{item_name} = {item_name} + %s, "
                update_player_query += f"{item_name} = 0, "
                params_server.append(player_quantity)

            if update_server_query == "":
                await ctx.send("You have no items to sell.")
                return

            update_server_query = update_server_query.rstrip(', ') + f" WHERE server_id = %s"
            params_server.append(server_id)
            await cursor.execute(update_server_query, params_server)

            update_player_query = update_player_query.rstrip(', ') + f" WHERE server_id = %s AND player_id = %s"
            params_player = [server_id, player_id]
            await cursor.execute(update_player_query, params_player)

            total_florins = await Database.give_florins(server_id, player_id, total_earned)
            await ctx.send(f"You've sold all your items for {total_earned} florins. You now have {total_florins} florins.")









#Selecting units
@bot.command(name="mystic", description="Select your Wizard from your owned cards", brief='select your mystic')
async def _select_mystic(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await Database.check_owned_cards(ctx, server_id, player_id, bot, pool, "mystic", allow_selection=True, role_type="mystic")
@bot.command(name="soldier", description="Select your Captain from your owned cards", brief='select your soldier')
async def _select_soldier(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await Database.check_owned_cards(ctx, server_id, player_id, bot, pool, "soldier", allow_selection=True, role_type="soldier")
@bot.command(name="rogue", description="Select your Rogue from your owned cards", brief='select your rogue')
async def _select_rogue(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await Database.check_owned_cards(ctx, server_id, player_id, bot, pool, "rogue", allow_selection=True, role_type="rogue")
@bot.command(name="patron", description="Select your patron from your owned cards", brief='select your patron')
async def _select_patron(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await Database.check_owned_cards(ctx, server_id, player_id, bot, pool, "patron", allow_selection=True, role_type="patron")









#Building claims
@bot.command(name="build", description="Select a building to target", brief='construct buildings')
async def build(ctx):
    bot = ctx.bot
    await JobFunctions._available_buildings(ctx, bot, conn, pool)
@bot.command(name="repair", description="Select a building to target", brief='repair buildings')
async def build(ctx):
    bot = ctx.bot
    await JobFunctions._rebuild(ctx, bot, conn, pool)








#Rogue Functions
@bot.command(name="sitem", description="Select an item to steal", brief='steal items from user')
async def steal(ctx, target_user: discord.Member):
    await JobFunctions._target_itemsteal(ctx, target_user, conn, pool)
@bot.command(name="scoin", description="Select a user to steal from", brief='steal florins from user')
async def steal(ctx, target_user: discord.Member):
    await JobFunctions._steal_florins(ctx, target_user, conn, pool)
@bot.command(name="kill", brief='kill a target\'s card')
async def assassinate(ctx, target_user: discord.Member):
    await JobFunctions._target_role(ctx, target_user, conn, pool)
@bot.command(name="capture", brief='capture a target\'s card')
async def capture(ctx, target_user: discord.Member):
    await JobFunctions._target_role_capture(ctx, target_user, conn, pool)







#Soldier Functions
@bot.command(name="pillage", description="Select an item to steal", brief='pillage target\'s building')
async def pillage(ctx, target_user: discord.Member):
    await JobFunctions._target_building(ctx, target_user, conn, pool)






#shop Items
@bot.command(name="shop", description="Open shop", brief='Buy Items')
async def _shop(ctx):
    bot = ctx.bot
    player_id = ctx.author.id
    server_id = ctx.guild.id
    await JobFunctions.show_random_items(ctx, server_id, player_id, conn, pool)







#Florins
collect_locks = {}
@bot.command(name='collect', brief='collect building income')
async def collect(ctx):
    user_id = ctx.author.id
    server_id = ctx.guild.id
    action = 'collect'

    has_aya_chosen_role = False

    if user_id not in collect_locks:
        collect_locks[user_id] = asyncio.Lock()

    async with collect_locks[user_id]:
        can_collect, remaining_time = await Database.can_perform_action(user_id, server_id, action, pool, conn)

        if not can_collect:
            await ctx.send(f"You cannot collect right now. Please wait {remaining_time}")
            return

        await Database.collect_income(ctx, bot)

        await Database.update_action_timestamp(user_id, server_id, action, has_aya_chosen_role)






# Race & Class
class StatPointAssignView(discord.ui.View):
    def __init__(self, remaining_stat_points, command_user):
        super().__init__(timeout=30)
        self.remaining_stat_points = remaining_stat_points
        self.command_user = command_user

    @discord.ui.button(label="Strength", style=discord.ButtonStyle.primary)
    async def strength_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        if self.remaining_stat_points > 0:
            await self.add_stat_point(interaction, 'strength')

    @discord.ui.button(label="Intellect", style=discord.ButtonStyle.primary)
    async def intellect_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        if self.remaining_stat_points > 0:
            await self.add_stat_point(interaction, 'intellect')

    @discord.ui.button(label="Agility", style=discord.ButtonStyle.primary)
    async def agility_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        if self.remaining_stat_points > 0:
            await self.add_stat_point(interaction, 'agility')

    @discord.ui.button(label="Constitution", style=discord.ButtonStyle.primary)
    async def constitution_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        if self.remaining_stat_points > 0:
            await self.add_stat_point(interaction, 'constitution')

    async def add_stat_point(self, interaction: discord.Interaction, stat):
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"""
                    UPDATE player_classes
                    SET {stat} = {stat} + 1, remaining_stat_points = remaining_stat_points - 1
                    WHERE player_id = %s AND server_id = %s
                """, (interaction.user.id, interaction.guild.id))
                await conn.commit()

        self.remaining_stat_points -= 1
        if self.remaining_stat_points <= 0:
            self.stop()

        await interaction.response.edit_message(
            content=f"You've added one point to {stat}! You have {self.remaining_stat_points} remaining stat points.")

@bot.command(name="lvlup", description="Assign remaining stat points", brief='spend your stat points')
async def assign_points(ctx):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT remaining_stat_points
                FROM player_classes
                WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is None:
                await ctx.send("You need to select a class first.")
                return

    remaining_stat_points = data[0]

    if remaining_stat_points <= 0:
        await ctx.send("You have no remaining stat points.")
        return

    view = StatPointAssignView(remaining_stat_points, ctx.author)
    await ctx.send(
        f"You have {remaining_stat_points} remaining stat points. Click a button to assign a point to that stat.",
        view=view)
@bot.command(name="start", description="Check your owned cards on the server")
async def _campaign(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await assign_specific_quest(ctx, server_id, player_id, bot)
@bot.command(name="continue", description="Check your owned cards on the server")
async def _continuec(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    await start_player_quest(ctx, server_id, player_id, bot)
async def assign_specific_quest(ctx, server_id, player_id, bot):
    quest_id = 1
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Check if player has already started the quest
            await cursor.execute("""
                SELECT 1
                FROM player_campaign_progress
                WHERE server_id = %s AND player_id = %s AND quest_id = %s
            """, (server_id, player_id, quest_id))

            already_started = await cursor.fetchone()

            if already_started:
                await ctx.send("You've already started the Tutorial, use ***$continue***")
                return

            # Fetch the specific quest details
            await cursor.execute("""
                SELECT cq.name, cq.total_stages, cq.image_url, cq.description, cq.reward
                FROM campaign_quests cq
                WHERE cq.id = %s
            """, (quest_id,))

            quest = await cursor.fetchone()

            if not quest:
                await ctx.send(f"No quest found with id: {quest_id}")
                return

            name, total_stages, image_url, description, reward = quest
            embed = discord.Embed(title=name)
            embed.set_image(url=image_url)


            message = await ctx.send(embed=embed)

            # Start the specific quest with stage 1
            await cursor.execute("""
                INSERT INTO player_campaign_progress (server_id, player_id, quest_id, player_stage)
                VALUES (%s, %s, %s, 1)
            """, (server_id, player_id, quest_id))

            await ctx.send(f"You have been assigned the quest '{name}'. Good luck!")
            await _continuec(ctx)


#Campaign 1
Dark_CONVERSATION_EMBEDS = {
    "Noble Coalition": discord.Embed(
        title="Secret Meeting: Noble Coalition",
        description="Cloaked in the shadows of the grand estate's lustrous gardens, you glimpse an uncanny sight. "
                    "Your representative, an ethereal Elven woman, engaged in a hushed dialogue with a formless "
                    "entity. The entity seems to coalesce from the shadows, its visage taking form "
                    "within the eerie green glimmer of a jade statue. An unsettling aura of ancient power "
                    "whispers in the air...",
        color=0x00ff00).set_image(url="https://imagizer.imageshack.com/img922/4937/29rZ0Z.png"),
    "The Ferocious Pact": discord.Embed(
        title="Secret Meeting: The Ferocious Pact",
        description="You tread carefully through the rambunctious camp, reaching the edges of a makeshift war-tent."
                    " Your representatives, a hardened orc war-chief and a wily goblin king, share harsh whispers "
                    "with a shrouded figure. Their words carry an edge of malice, spitting cruel intentions towards "
                    "the other factions, like venom dripping off a snake's fangs...",
        color=0xff0000).set_image(url="https://imagizer.imageshack.com/img924/5769/EepE5j.png"),
    "Stout Alliance": discord.Embed(
        title="Secret Meeting: Stout Alliance",
        description="Hidden by the humming forges and sturdy architecture, you find a hushed meeting in progress. "
                    "Your dwarven and gnome representatives, masters of their respective crafts, strategize with a "
                    "shadowy figure. Their discourse is grounded in pragmatism, weaving plans to manipulate the "
                    "escalating tensions for profit. Their influence extending beyond the anvil and gears...",
        color=0x0000ff).set_image(url="https://imagizer.imageshack.com/img924/6594/Pp41W5.png"),
}
INTRO_EMBEDS = {
    "Noble Coalition": discord.Embed(
        title="Lady Eolande Sylvari",
        description="As you step forth in the grand meeting chamber, your eyes are drawn to a gathering of dignified beings. Impeccably dressed elves intermingle with stately humans, their golden banners embroidered with symbols of peace and prosperity. Here, wisdom and culture intertwine, creating a harmony that echoes in the very air of the chamber. To earn their trust, your words must resonate with respect and sincerity...",
        color=0x00ff00).set_image(url="https://imagizer.imageshack.com/img922/7332/Etbda8.png").set_footer(text="Lady Eolande Sylvari scans you briefly, a bored expression on her face. 'Another recruit... Tell me quickly, what makes you worth my time?'"),
    "The Ferocious Pact": discord.Embed(
        title="Grukk Thunderfist",
        description="Stepping into the dimly lit chamber, the air is thick with tension and anticipation. Stern-faced orcs tower above, their fierce eyes gleaming, as goblins skulk in the shadows, their cunning gaze never straying far. Their banners of black and red depict their strength and relentless determination. To win their respect, you must demonstrate courage and tenacity...",
        color=0xff0000).set_image(url="https://imagizer.imageshack.com/img922/5259/MFjVXD.png").set_footer(text="Grukk Thunderfist glares at you, his hand twitching toward his blade. 'A fresh recruit, or fresh meat... what's your worth, worm?'"),
    "Stout Alliance": discord.Embed(
        title="Thoren Ironbeard",
        description="Entering the grand chamber, you are met with the comforting warmth of the hearth. Underneath low-hanging chandeliers, the sturdy dwarves and industrious gnomes share stories over mugs of ale. Their blue banners are a testament to their relentless dedication to craftsmanship and industry. To win their approval, your deeds must be as sturdy as their faith in the forge...",
        color=0x0000ff).set_image(url="https://imagizer.imageshack.com/img924/9531/vropRr.png").set_footer(text="Thoren Ironbeard barely glances up from his work. 'Another hand looking for work... What skills do you have?'"),
}
SNEAK_EMBEDS_SUCCESS = {
    "Noble Coalition": discord.Embed(
        title="Sneak: Noble Coalition",
        description="You successfully sneak upon the noble elves and humans...",
        color=0x00ff00).set_image(url="https://imagizer.imageshack.com/img922/6057/bEs1AK.png"),
    "The Ferocious Pact": discord.Embed(
        title="Sneak: The Ferocious Pact",
        description="You successfully sneak upon the fierce orcs and goblins...",
        color=0xff0000).set_image(url="https://imagizer.imageshack.com/img923/9307/u5XPqu.png"),
    "Stout Alliance": discord.Embed(
        title="Sneak: Stout Alliance",
        description="You successfully sneak upon the sturdy dwarves and gnomes...",
        color=0x0000ff).set_image(url="https://imagizer.imageshack.com/img924/8214/KcsfTm.png"),
}
RACE_FACTIONS = {
    "Elf": "Noble Coalition",
    "Human": "Noble Coalition",
    "Orc": "The Ferocious Pact",
    "Goblin": "The Ferocious Pact",
    "Dwarf": "Stout Alliance",
    "Gnome": "Stout Alliance",
}
FACTION_EMBEDS = {
    "Noble Coalition": discord.Embed(
        title="Noble Coalition",
        description="Upon reaching the grand estate, you're greeted by lush gardens, and the building radiates an air "
                    "of serenity. Gilded banners depicting graceful elves and noble humans flutter in the breeze. "
                    "The aura of wisdom and culture is almost tangible. As you approach to introduce yourself, "
                    "you feel an instinctive need to show respect and sincerity...",
        color=0x00ff00).set_image(url="https://imagizer.imageshack.com/img922/1601/xJu9Ct.png"),
    "The Ferocious Pact": discord.Embed(
        title="The Ferocious Pact",
        description="You find yourself standing before a sprawling, disordered encampment. The harsh scent of "
                    "fire and iron fills the air. Banners of black and red, bearing the fierce symbols of orcs "
                    "and cunning images of goblins, flap wildly in the wind. The sense of raw determination and "
                    "strength is palpable. As you steel yourself to introduce your presence, you feel a surge of"
                    " courage and tenacity...",
        color=0xff0000).set_image(url="https://imagizer.imageshack.com/img923/996/bD8Oiu.png"),
    "Stout Alliance": discord.Embed(
        title="Stout Alliance",
        description="Before you lies a humble dwarven district, marked by stout stone buildings and the distant "
                    "sound of hammering metal. Blue banners display the proud figures of hardy dwarves and industrious"
                    " gnomes, fluttering in the crisp mountain breeze. The hard-working ethos of the place echoes "
                    "in the clinking of tools and the glowing forges. As you prepare to introduce yourself, "
                    "you know that your deeds must speak as loudly as the resounding hammers...",
        color=0x0000ff).set_image(url="https://imagizer.imageshack.com/img922/3934/eAmHs0.png"),
}
SKILL_EMBEDS = {
    "Stealth": discord.Embed(
        title="Stealth",
        description="Characters adept in Stealth are skilled at moving quietly and staying hidden, often developed from a necessity to stay unnoticed in dangerous environments or as part of their profession such as thieving or reconnaissance.",
        color=0x2ECC71).set_image(url="https://imagizer.imageshack.com/img923/7135/o1n8Ut.png"),
    "Acrobatics": discord.Embed(
        title="Acrobatics",
        description="Acrobatics skills usually arise from training or a natural talent for nimble movement. Characters with this skill may have been performers, athletes, or simply survived by deftly navigating the rooftops of their city.",
        color=0xE67E22).set_image(url="https://imagizer.imageshack.com/img922/4789/UywM6k.png"),
    "Deception": discord.Embed(
        title="Deception",
        description="Those skilled in Deception have learned to mask the truth, often out of necessity in the world of politics, or crime. They can convincingly portray lies and are adept at impersonating others.",
        color=0x8E44AD).set_image(url="https://imagizer.imageshack.com/img924/5743/mtQauE.png"),
    "Insight": discord.Embed(
        title="Insight",
        description="Insight is often developed by individuals who have a keen sense of human nature, often as a result of experience in dealing with people from all walks of life such as priests, judges, or innkeepers.",
        color=0x3498DB).set_image(url="https://imagizer.imageshack.com/img923/6978/mWqcJa.png"),
    "Intimidation": discord.Embed(
        title="Intimidation",
        description="Characters with this skill have learned to instill fear in others. This might be due to their past as a soldier, gang member, or a solitary predator who had to scare off threats rather than fight.",
        color=0xC0392B).set_image(url="https://imagizer.imageshack.com/img923/1581/n8yTfA.png"),
    "Investigation": discord.Embed(
        title="Investigation",
        description="This skill is common among detectives, scholars, and explorers who have spent much of their lives piecing together clues and deductions to uncover truth that's not immediately apparent.",
        color=0x9B59B6).set_image(url="https://imagizer.imageshack.com/img923/9761/wr55ru.png"),
    "Medicine": discord.Embed(
        title="Medicine",
        description="Knowledge in Medicine often comes from academic study or practical necessity. Healers, field medics, or anyone who has had to care for the sick or injured would have developed this skill.",
        color=0x1ABC9C).set_image(url="https://imagizer.imageshack.com/img923/4931/Lz65BG.png"),
    "Religion": discord.Embed(
        title="Religion",
        description="This skill is typically found among priests, scholars, or devout believers who have spent a significant portion of their lives studying the lore and dogma of different faiths.",
        color=0xF1C40F).set_image(url="https://imagizer.imageshack.com/img924/879/0AcGjg.png"),
    "Persuasion": discord.Embed(
        title="Persuasion",
        description="Persuasion skills often develop in those who frequently interact with others in a way that requires influencing people. Diplomats, merchants, and nobility often have this skill.",
        color=0xE74C3C).set_image(url="https://imagizer.imageshack.com/img922/833/0wRDER.png"),
    "Performance": discord.Embed(
        title="Performance",
        description="Artists, bards, actors, and entertainers usually possess the Performance skill. It represents their ability to captivate an audience with their talent.",
        color=0xFFC312).set_image(url="https://imagizer.imageshack.com/img924/291/7pu2q3.png"),
    "Perception": discord.Embed(
        title="Perception",
        description="Perception skills are often honed by individuals who need to be aware of their surroundings. Hunters, guards, and wilderness survivalists typically excel in Perception.",
        color=0x3498DB).set_image(url="https://imagizer.imageshack.com/img923/6134/aLwEda.png"),
    "Arcana": discord.Embed(
        title="Arcana",
        description="The Arcana skill is common among wizards, scholars and sages who have studied magical theory and history. It's also seen in other spellcasters or people with a keen interest in the arcane arts.",
        color=0x9B59B6).set_image(url="https://imagizer.imageshack.com/img922/7109/JnjyHh.png"),
}
SKILL_NAMES = [
    "Stealth",
    "Acrobatics",
    "Deception",
    "Insight",
    "Intimidation",
    "Investigation",
    "Medicine",
    "Religion",
    "Persuasion",
    "Performance",
    "Perception",
    "Arcana",
]
INTRO_INTERACTION_EMBEDS = {
    "Noble Coalition": discord.Embed(
        title="Lady Eolande Sylvari",
        description="Lady Eolande Sylvari surveys you with an arched brow, 'What strength can you lend to our cause, adventurer?'",
        color=0x00ff00).set_image(url="https://imagizer.imageshack.com/img922/7332/Etbda8.png"),
    "The Ferocious Pact": discord.Embed(
        title="Grukk Thunderfist",
        description="Grukk Thunderfist grunts, fixing you with a stern gaze, 'What blood and sweat do you bring to the battlefields, small one?'",
        color=0xff0000).set_image(url="https://imagizer.imageshack.com/img922/5259/MFjVXD.png"),
    "Stout Alliance": discord.Embed(
        title="Thoren Ironbeard",
        description="Thoren Ironbeard and Fizzbin Gearspark glance at each other, before Thoren rumbles, 'What skills and ingenuity do you offer to strengthen our ranks?'",
        color=0x0000ff).set_image(url="https://imagizer.imageshack.com/img924/9531/vropRr.png"),
}
INTRO_INTERACTION_EMBEDS2 = {
    "Noble Coalition": discord.Embed(
        title="Lady Eolande Sylvari",
        description="Lady Eolande offers a brief nod, pushing a small bag across the table to you. 'A modest fund of 250 florins to get you started. Our expectations are high. Make us proud.'",
        color=0x00ff00).set_image(url="https://imagizer.imageshack.com/img922/7332/Etbda8.png"),
    "The Ferocious Pact": discord.Embed(
        title="Grukk Thunderfist",
        description="Grukk grunts, tossing a sack of coins at you. '250 florins. Show us your worth on the battlefield. Contribute. Prove your mettle.'",
        color=0xff0000).set_image(url="https://imagizer.imageshack.com/img922/5259/MFjVXD.png"),
    "Stout Alliance": discord.Embed(
        title="Thoren Ironbeard",
        description="Thoren slides a hefty pouch towards you, a serious look in his eyes. 'Here are 250 florins. We believe in deeds, not words. Strengthen our alliance with your actions.'",
        color=0x0000ff).set_image(url="https://imagizer.imageshack.com/img924/9531/vropRr.png"),
}

class ProfessionSelectView(discord.ui.View):
    def __init__(self, ctx, professions, profession_keys, pool, command_user):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.professions = professions
        self.profession_keys = profession_keys
        self.current_profession_index = 0
        self.pool = pool
        self.command_user = command_user

    async def generate_embed(self, profession_key):
        profession_details = self.professions[profession_key]
        embed = discord.Embed(title=profession_details['header'], description=profession_details['description'],
                              color=profession_details['color'])
        embed.set_image(url=profession_details['image_url'])
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_profession_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_profession_index = (self.current_profession_index - 1) % len(self.profession_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.profession_keys[self.current_profession_index]))

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_profession_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_profession_index = (self.current_profession_index + 1) % len(self.profession_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.profession_keys[self.current_profession_index]))

    @discord.ui.button(emoji="<:Select:1108065587587993650>", style=discord.ButtonStyle.primary)
    async def select_profession_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        selected_profession = self.profession_keys[self.current_profession_index]

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    # Inserting player's profession
                    await cur.execute("""
                        INSERT INTO player_professions (server_id, player_id, job_name, image_url, job_level, EXP, remaining_stat_points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.ctx.guild.id,
                        self.ctx.author.id,
                        selected_profession,
                        self.professions[selected_profession]['image_url'],
                        1,
                        0,
                        0
                    ))

                    await conn.commit()
                    await self.ctx.send(f"You have selected {selected_profession} as your profession")
                    self.stop()
                except:
                    self.stop()

async def select_profession(ctx):
    bot = ctx.bot

    professions = {
        'Smith': {
            'image_url': "https://imagizer.imageshack.com/img922/4259/SMITH_URL.png",
            'description': '- Smithing skills...',
            'header': 'Smith',
            'color': 0x8B4513,
        },
        'Chef': {
            'image_url': "https://imagizer.imageshack.com/img922/4259/CHEF_URL.png",
            'description': '- Chef skills...',
            'header': 'Chef',
            'color': 0x006400,
        },
        'Alchemist': {
            'image_url': "https://imagizer.imageshack.com/img922/4259/ALCHEMIST_URL.png",
            'description': '- Alchemist skills...',
            'header': 'Alchemist',
            'color': 0x8B4513,
        },
        'Tinker': {
            'image_url': "https://imagizer.imageshack.com/img922/4259/TINKER_URL.png",
            'description': '- Tinker skills...',
            'header': 'Tinker',
            'color': 0xFFD700,
        },
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT job_name FROM player_professions WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                await ctx.send("You've already selected a profession.")
                return

    profession_keys = list(professions.keys())

    view = ProfessionSelectView(ctx, professions, profession_keys, pool, ctx.author)
    message = await ctx.send(embed=await view.generate_embed(profession_keys[0]), view=view)
class SkillSelectView(discord.ui.View):
    def __init__(self, ctx, player_id, server_id, pool, command_user, faction, remaining_points):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.player_id = player_id
        self.server_id = server_id
        self.pool = pool
        self.command_user = command_user
        self.remaining_points = remaining_points
        self.skill_keys = None
        self.current_skill_index = 0
        self.faction = faction

    async def populate_skill_keys(self):
        self.skill_keys = []
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                for skill_name in SKILL_NAMES:
                    await cur.execute(f"""
                        SELECT {skill_name} 
                        FROM player_feats 
                        WHERE player_id = %s AND server_id = %s
                    """, (self.player_id, self.server_id))
                    skill_points = await cur.fetchone()
                    if not skill_points or skill_points[0] == 0:
                        self.skill_keys.append(skill_name)
        self.current_skill_index = 0

    async def generate_embed(self, skill_key):
        embed = SKILL_EMBEDS[skill_key]
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_skill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_skill_index = (self.current_skill_index - 1) % len(self.skill_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.skill_keys[self.current_skill_index]))

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_skill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_skill_index = (self.current_skill_index + 1) % len(self.skill_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.skill_keys[self.current_skill_index]))

    async def create_followup_embed(self, skill, points_left):
        confirmation_embed = discord.Embed(
            title=f"You picked {skill}",
            description=f"You now have {points_left} point(s) left.",
            color=discord.Color.green()
        )
        # Use the image of the skill as the thumbnail
        confirmation_embed.set_thumbnail(url=SKILL_EMBEDS[skill].image.url)
        return confirmation_embed

    @discord.ui.button(emoji="<:Select:1108065587587993650>", style=discord.ButtonStyle.primary)
    async def select_skill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        if self.remaining_points > 0:
            selected_skill = self.skill_keys[self.current_skill_index]
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    try:
                        await cur.execute(f"""
                            UPDATE player_feats 
                            SET {selected_skill} = {selected_skill} + 1, Remaining_Points = Remaining_Points - 1
                            WHERE server_id = %s AND player_id = %s
                        """, (self.server_id, self.player_id))
                        await conn.commit()
                        self.remaining_points -= 1
                        self.skill_keys.remove(selected_skill)  # Remove selected skill from the list
                        if self.remaining_points == 0 or len(self.skill_keys) == 0:
                            await interaction.response.edit_message(embed=await self.generate_embed(
                                self.skill_keys[self.current_skill_index] if self.skill_keys else selected_skill))
                            await interaction.followup.send(embed=await self.create_followup_embed(selected_skill, self.remaining_points))
                            await interaction.followup.send(embed=INTRO_INTERACTION_EMBEDS2[self.faction])
                            await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 8)
                            await _continuec(self.ctx)
                            self.stop()
                        else:
                            self.current_skill_index = 0
                            await interaction.response.edit_message(embed=await self.generate_embed(self.skill_keys[self.current_skill_index]))
                            await interaction.followup.send(embed=await self.create_followup_embed(selected_skill, self.remaining_points))
                    except Exception as e:
                        print(f"Failed to execute query: {e}")
async def select_skill(ctx, faction):
    bot = ctx.bot
    guild_idz = 1104234202624426038
    guildz = bot.get_guild(guild_idz)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT Remaining_Points FROM player_feats WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()

            # If not, create a new entry with default values
            if data is None:
                await cur.execute("""
                    INSERT INTO player_feats (server_id, player_id, Remaining_Points)
                    VALUES (%s, %s, %s)
                """, (ctx.guild.id, ctx.author.id, 3))
                await conn.commit()
                data = [3]

            # If player already selected all skills
            elif data[0] <= 0:
                await ctx.send("You've already selected all your skills.")
                return

    view = SkillSelectView(ctx, ctx.author.id, ctx.guild.id, pool, ctx.author, faction,
                           data[0])
    await view.populate_skill_keys()
    message = await ctx.send(embed=await view.generate_embed(view.skill_keys[0]), view=view)
class RaceRepApproachView(discord.ui.View):
    def __init__(self, ctx, player_race, player, agility, command_user):
        super().__init__()
        self.ctx = ctx
        self.player_race = player_race
        self.player = player
        self.faction = RACE_FACTIONS[self.player_race]
        self.agility = agility
        self.command_user = command_user
        self.server_id = ctx.guild.id

    async def generate_embed(self):
        return FACTION_EMBEDS[self.faction]

    @discord.ui.button(label="Sneak up on", style=discord.ButtonStyle.primary)
    async def sneak_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        if self.agility >= 5:
            await self.ctx.send(embed=SNEAK_EMBEDS_SUCCESS[self.faction])
            await self.ctx.send(embed=Dark_CONVERSATION_EMBEDS[self.faction], view=RaceRepApproachView(self.ctx, self.player_race, self.player, self.agility, self.command_user))
        else:
            failure_embed = discord.Embed(description=f"Your attempt to sneak upon {self.faction} has failed...",
                                          color=discord.Color.red())
            await self.ctx.send(embed=failure_embed)
            await self.introduce.callback(interaction)

    @discord.ui.button(label="Introduce", style=discord.ButtonStyle.secondary)
    async def introduce(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        await self.ctx.send(embed=INTRO_EMBEDS[self.faction])
        await select_skill(self.ctx, self.faction)
async def approach_race_representative(ctx, player_id, server_id):
    # Use a connection pool to connect to the database.
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Get player's race from the database
            await cur.execute("""
                SELECT player_race FROM player_races WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                player_race = data[0]
            else:
                await ctx.send("You haven't chosen a race yet.")
                return
    agility_value = (await get_player_statsQ(player_id, server_id))['agility']
    view = RaceRepApproachView(ctx, player_race, ctx.author, agility_value, ctx.author)
    embed = await view.generate_embed()
    await ctx.send(embed=embed, view=view)
async def select_race(ctx):
    bot = ctx.bot
    guild_idz = 1104234202624426038
    emoji_Rarrow = 1106624275034677360
    emoji_Larrow = 1106624302268297286
    emoji_Select = 1108065587587993650
    guildz = bot.get_guild(guild_idz)
    Larrow = discord.utils.get(guildz.emojis, id=emoji_Larrow)
    Rarrow = discord.utils.get(guildz.emojis, id=emoji_Rarrow)
    Select = discord.utils.get(guildz.emojis, id=emoji_Select)
    race_descriptions = {
        'Goblin': "Your roots lie in the sprawling labyrinth of junkyards and shanties. "
                  "This chaotic mosaic is home to ingenious inventors, sly merchants, and shrewd "
                  "scavengers. As one from such diverse chaos, you've developed a knack for seeing "
                  "value where others see only waste. Regardless of your unique qualities, you are "
                  "undeniably a child of resilience and resourcefulness, moulded by a world that "
                  "thrives in seeming disarray.",
        'Orc': "Your origins trace back to the desolate outer realms, a testament to survival"
               " in its purest form. It's a harsh, barren land that breeds the strongest warriors and "
               "most enduring survivors. While the world may see Orcs as brute savages, your people "
               "understand the true value of strength and the raw purity of survival. No matter your "
               "individual path, the spirit of endurance courses through your veins.",
        'Human': "Born a Human, you come from the world's ruling order. From bustling metropolises to "
                 "fortified castles, your people have cultivated a society built on law, diplomacy, "
                 "and commerce. While humans are diverse, most bear the weight of expectation, duty, "
                 "and the complex dance of politics. No matter your personal beliefs or aspirations, "
                 "your background has been shaped by the rigors of leadership and governance.",
        'Dwarf': "Your lineage is interwoven with the rich veins of the hills and "
                 "mountains. Your forebears carved grand halls and vast cities into the rock itself,"
                 " keeping mostly to themselves and the secrets of the earth. Dwarven society values "
                 "craftsmanship, mining the deepest veins of gold and gemstones and forging legendary "
                 "artifacts. Regardless of your personal journey, you bear the resilience and the "
                 "wisdom of the mountains in your heart.",
        'Gnome': "You belong to a race of ingenious inventors and wise scholars. "
                 "Living primarily underground, your society thrives on innovation, intellectual "
                 "curiosity, and the magic underlying the fabric of reality. Gnomes have given "
                 "the world some of its most fantastic and complex machinery, and their revolutionary"
                 " discoveries often challenge the world's understanding. Even if you deviate from the "
                 "stereotype, the thirst for knowledge is a part of your heritage.",
        'Elf': "You are one with nature's wisdom and ancient magic. "
               "Your people dwell in forest kingdoms, secluded from the hustle of the world, "
               "living in harmony with the ancient woods. Elven society is one of tradition, "
               "magic, and a deep-rooted respect for nature, often considered aloof or whimsical "
               "by other races. While you as an individual may chart your own course, you cannot "
               "deny the melodic whisper of the ancient forests in your soul."
    }
    races = {
        'Gnome': {
            'image_url': "https://imagizer.imageshack.com/img924/163/zNIDW5.png",
            'description': '- Inventiveness: Increase INT stat\n points by 3.\n- Quick Thinking: 0.4% chance\n per INT point to avoid a negative\n outcome',
            'header': 'Gnomes',
            'footer': 'Stout Alliance Dwarves & Gnomes',
            'color': 0x00FFFF
        },
        'Dwarf': {
            'image_url': "https://imagizer.imageshack.com/img923/4334/ajPn44.png",
            'description': '- Resilience: Increase CON stat\n points by 3.\n- Stoneform: 0.4% chance per\n CON point to resist an incoming\n attack completely.',
            'header': 'Dwarves',
            'footer': 'Stout Alliance Dwarves & Gnomes',
            'color': 0x800080
        },
        'Human': {
            'image_url': "https://imagizer.imageshack.com/img924/3717/FVsev4.png",
            'description': '- Adaptability: Increase all stat\n points by 1.\n- Ingenuity: 0.2% chance per INT\n point to roll with advantage',
            'header': 'Humans',
            'footer': 'Noble Coalition Elves & Humans',
            'color': 0xFFA500
        },
        'Elf': {
            'image_url': "https://imagizer.imageshack.com/img924/736/hjH7vu.png",
            'description': '- Grace: Increase AGI and INT stat\n points by 2/1.\n- Elven Insight: 0.5% chance per\n INT point to foresee an enemy\'s\n action and take preventive\n measures.',
            'header': 'Elves',
            'footer': 'Noble Coalition Elves & Humans',
            'color': 0x008000
        },
        'Goblin': {
            'image_url': "https://imagizer.imageshack.com/img924/2347/6azpHy.png",
            'description': '- Cunning: Increase AGI and INT\n stat points by 1/2.\n- Trickery: 0.4% chance per AGI to\n keep florins when making a\n purchase',
            'header': 'Goblins',
            'footer': 'Ferocious Pact Orcs & Goblins',
            'color': 0xFF00FF
        },
        'Orc': {
            'image_url': "https://imagizer.imageshack.com/img923/8652/BsFfDy.png",
            'description': '- Brutality: Increase STR stat\n points by 3.\n- Berserk: 0.4% chance per STR\n point to double the attack\n damage.',
            'header': 'Orcs',
            'footer': 'Ferocious Pact Orcs & Goblins',
            'color': 0xFF0000
        },
    }
    allies = {
        'Gnome': ['Dwarf', 'Gnome'],
        'Dwarf': ['Gnome', 'Dwarf'],
        'Human': ['Elf', 'Human'],
        'Elf': ['Human', 'Elf'],
        'Orc': ['Goblin', 'Orc'],
        'Goblin': ['Orc', 'Goblin']
    }
    racial_abilities = {
        'Gnome': (1, 0, 0),
        'Dwarf': (1, 0, 0),
        'Human': (1, 0, 0),
        'Elf': (1, 0, 0),
        'Orc': (1, 0, 0),
        'Goblin': (1, 0, 0)
    }

    race_keys = list(races.keys())
    current_race_index = 0

    def generate_embed(race_key):
        race_details = races[race_key]
        embed = discord.Embed(title=race_details['header'], description=race_details['description'],
                              color=race_details['color'])
        embed.set_image(url=race_details['image_url'])
        embed.set_footer(text=race_details['footer'])
        return embed

    # Check if the player already has a race
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT player_race FROM player_races WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                await ctx.send("You've already selected a race.")
                await update_player_stage(ctx.guild.id, ctx.author.id, 2)
                return

    message = await ctx.send(embed=generate_embed(race_keys[current_race_index]))

    await message.add_reaction(f"{Larrow}")
    await message.add_reaction(f"{Rarrow}")
    await message.add_reaction(f"{Select}")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in [str(Larrow), str(Rarrow), str(Select)]

    while True:
        try:
            reaction, user = await ctx.bot.wait_for("reaction_add", timeout=180, check=check)

            if str(reaction.emoji) == str(Rarrow):
                current_race_index = (current_race_index + 1) % len(race_keys)
            elif str(reaction.emoji) == str(Larrow):
                current_race_index = (current_race_index - 1) % len(race_keys)

            if str(reaction.emoji) == str(Select):
                selected_race = race_keys[current_race_index]

                try:
                    async with pool.acquire() as conn:
                        async with conn.cursor() as cur:
                            await cur.execute("""
                                INSERT INTO player_races (server_id, player_id, player_race, gnome_allied, human_allied, orc_allied, goblin_allied, dwarf_allied, elf_allied, racial_1, racial_2, racial_3)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                ctx.guild.id,
                                ctx.author.id,
                                selected_race,
                                'Gnome' in allies[selected_race],
                                'Human' in allies[selected_race],
                                'Orc' in allies[selected_race],
                                'Goblin' in allies[selected_race],
                                'Dwarf' in allies[selected_race],
                                'Elf' in allies[selected_race],
                                *racial_abilities[selected_race]
                            ))
                            await conn.commit()

                            # Send an embed message after successful selection.
                            embed = discord.Embed(
                                title=f"Race Selected: {selected_race}",
                                description=f"{race_descriptions[selected_race]}",
                                color=races[selected_race]['color']
                            )
                            embed.set_thumbnail(url=races[selected_race]['image_url'])
                            await ctx.send(embed=embed)

                            await update_player_stage(ctx.guild.id, ctx.author.id, 2)
                            await _continuec(ctx)

                except Exception as e:
                    print(f"Error occurred: {e}")  # log the error
                    await update_player_stage(ctx.guild.id, ctx.author.id, 1)
                    return

            await message.edit(embed=generate_embed(race_keys[current_race_index]))
            await message.remove_reaction(reaction, user)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            break
class ContractSigningView(discord.ui.View):
    def __init__(self, ctx, server_id, player_id, intellect_value, command_user):
        super().__init__()
        self.ctx = ctx
        self.server_id = server_id
        self.player_id = player_id
        self.intellect_value = intellect_value
        self.command_user = command_user

    async def generate_embed(self):
        embed = discord.Embed(
            title="Contract",
            description="The Guild Master slides a parchment towards you...",
            color=0x00ff00)
        embed.set_image(url="https://imagizer.imageshack.com/img922/5739/ELsgqf.png")
        return embed

    @discord.ui.button(label="Sign", style=discord.ButtonStyle.danger)
    async def sign_contract_direct(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                florins = await Database.get_florins(self.server_id, self.player_id)
                if florins < 50:
                    embed = discord.Embed(title="Insufficient Florins",
                                          description="The Guild Master eyes you disdainfully. "
                                                      "'You need at least 10 florins to show your commitment to the Guild's cause.'",
                                          color=0xff0000)
                    await self.ctx.send(embed=embed)
                    return

                embed = discord.Embed(title="Contract Signed - Choice Recorded",
                                      description="With a swift stroke, you sign the contract, aligning your future with the whims of the Guild. "
                                                  "The Guild Master nods in approval, 'The guild welcomes your commitment.'",
                                      color=0x00ff00)
                await self.ctx.send(embed=embed)
                await cur.execute("""
                    UPDATE player_campaign_progress
                    SET choice='signed'
                    WHERE server_id=%s AND player_id=%s
                """, (self.server_id, self.player_id))
                await conn.commit()
                await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 7)
                await Database.deduct_florins(self.server_id, self.player_id, 50)
                await _continuec(self.ctx)

    @discord.ui.button(label="Inspect (INT)", style=discord.ButtonStyle.primary)
    async def sign_contract(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                florins = await Database.get_florins(self.server_id, self.player_id)
                if florins < 10:
                    embed = discord.Embed(title="Insufficient Florins",
                                          description="The Guild Master eyes you disdainfully. "
                                                      "'You need at least 10 florins to show your commitment to the Guild's cause.'",
                                          color=0xff0000)
                    await self.ctx.send(embed=embed)
                    return

                embed = discord.Embed()
                embed.color = 0x00ff00
                if self.intellect_value <= 3:
                    embed.title = "Signed - Choice Recorded"
                    embed.description = "With a brash confidence that transcends the complex intricacies of the parchment, " \
                                        "you pledge your allegiance to the Guild. The Guild Master eyes you with a " \
                                        "hint of contempt. 'Very well. Welcome to the heart of adventure in Syloria.'"
                elif self.intellect_value <= 5:
                    embed.title = "Messy Signed - Choice Recorded"
                    embed.description = "The fine print on the contract sparks a shadow of doubt in your mind, " \
                                        "but you sign nonetheless, making your signature as messy and ineligible as possible." \
                                        " feeling the gravity of your choice as your pen lifts."
                else:
                    embed.title = "Fake Signed - Choice Recorded"
                    embed.description = "The contract is riddled with cleverly disguised clauses and conditions. " \
                                        "Understanding the gravity of the document, you subtly use a trick you'd learnt - " \
                                        "signing in a mystical ink that would vanish within a fortnight"

                await self.ctx.send(embed=embed)
                await cur.execute("""
                    UPDATE player_campaign_progress
                    SET choice='{}signed'
                    WHERE server_id=%s AND player_id=%s
                """.format('fake ' if self.intellect_value > 5 else ''),
                                   (self.server_id, self.player_id))
                await conn.commit()
                await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 7)
                await Database.deduct_florins(self.server_id, self.player_id, 10)
                await _continuec(self.ctx)
async def review_contract(ctx, server_id, player_id):
    intellect_value = (await get_player_statsQ(player_id, server_id))['intellect']
    view = ContractSigningView(ctx, server_id, player_id, intellect_value, ctx.author)
    embed = await view.generate_embed()
    await ctx.send(embed=embed, view=view)
class ClassSelectView(discord.ui.View):
    def __init__(self, ctx, classes, class_keys, pool, command_user):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.classes = classes
        self.class_keys = class_keys
        self.current_class_index = 0
        self.pool = pool
        self.command_user = command_user
        self.class_descriptions = {
                'Orc': {
                    'Warrior': "As an Orc Warrior, your heritage of survival in harsh conditions coupled with the "
                               "battle-hardened discipline of the warrior class make you a formidable force on the "
                               "battlefield. You use your strength and endurance to face any challenge, no matter how "
                               "insurmountable it may seem.",
                    'Mage': "The Orc Mage is a rare sight, blending the raw strength and survival instincts of your orcish "
                            "blood with the arcane knowledge of the Mage class. While you may appear to be a contradiction, "
                            "you are a force of nature, wielding both brute strength and destructive magic.",
                    'Rogue': "As an Orc Rogue, you utilize your physical prowess and cunning to take down your enemies. Your "
                             "Orcish heritage gives you a surprising advantage in the shadows, your size and strength enabling "
                             "brutal and efficient stealth attacks.",
                },
                'Gnome': {
                    'Warrior': "Gnome Warriors are an uncommon sight, but those who choose this path command great respect. "
                               "Wielding an intricate arsenal of mechanical weaponry, Gnome Warriors blend raw strength with "
                               "technological prowess, turning each battle into a spectacle of ingenious inventiveness.",

                    'Mage': "The Gnome Mages are renowned for their cerebral approach to magic. Harnessing the inherent "
                            "energies of the cosmos, they construct complex devices and contraptions that manipulate arcane "
                            "forces. This blend of intellect and magic marks them as some of the most innovative spellcasters "
                            "in Eldoria.",

                    'Rogue': "Stealth, cunning, and mischief -- the Gnome Rogues embody all these traits. Using their "
                             "mechanical gadgets and quick wit, they can sneak and deceive their way out of any situation. "
                             "Their trickery is not out of malice, but survival and a dash of playful curiosity.",
                },
                'Human': {
                    'Warrior': "As a Human Warrior, you were born into a society built on law and order, but your heart called "
                               "you to the battlefield. Trained in the metropolises' rigorous academies, you've learned the art"
                               " of war and carry the expectation and duty to protect your people.",
                    'Mage': "You, a Human Mage, are a beacon of knowledge and magic in a world of politics and diplomacy. From "
                            "the great libraries of the fortresses, you've learned to harness the raw energies of the universe, "
                            "juxtaposing the structured nature of human society with the wild potential of arcane power.",
                    'Rogue': "A Human Rogue, you move in the shadows of the metropolises, blending the art of subtlety with the"
                             " complexities of human politics. In a world where power is as much about secrets as armies, you"
                             " are the unseen hand that can tip the scales.",
                },
                'Elf': {
                    'Warrior': "As an Elven Warrior, you have mastered the delicate balance of grace and power. "
                               "Your blade dances in harmony with the ancient magic pulsing within you, rendering "
                               "you a formidable adversary in the battlefield. The forest whispers the tales of your "
                               "bravery and wisdom to every leaf and every creature within its realm.",
                    'Mage': "As an Elven Mage, your spells weave the whispers of the ancient forests into reality. "
                            "Your arcane knowledge hails from generations of magical traditions, intertwined with "
                            "the wisdom of nature itself. The woodland creatures bow in reverence to your harmonious "
                            "magic, echoing your spells in their songs.",
                    'Rogue': "As an Elven Rogue, you are as elusive as the forest's breeze and as deadly as its "
                             "predators. Your agility, combined with your deep understanding of nature, renders "
                             "you invisible in the underbrush, striking when least expected. The whispers of your "
                             "stealthy exploits travel from tree to tree, warning the woodland inhabitants of your "
                             "silent presence.",
                },
                'Dwarf': {
                    'Warrior': "Hailing from the grand stone halls of your mountain kingdom, as a Dwarf Warrior, "
                               "you're a testament to the endurance and strength of your people. Your kin have mined "
                               "deep veins of gold and gemstones, and the same resilience of the mountains runs through "
                               "your veins. Your upbringing in the art of combat and the crafting of weapons ensures "
                               "that you are a force to be reckoned with in any battle.",

                    'Mage': "As a Dwarf Mage, your deep connection to the earth's minerals and ores has allowed you "
                            "to tap into a unique form of magic. Your kin may be known for their craftsmanship and "
                            "strength, but you've proven that the scholarly arts are not beyond the reach of a dwarf. "
                            "Combining the traditional dwarven resilience with the arcane arts, you are truly a unique "
                            "presence in any magical gathering.",

                    'Rogue': "Being a Dwarf Rogue is a unique path to tread. While your kin are renowned warriors "
                             "and masterful crafters, you've chosen the shadows. Using your natural dwarven resilience "
                             "and the nimbleness uncommon among your kin, you strike from the unseen. This combination "
                             "of stealth and sturdiness makes you an unexpected adversary.",
                },
                'Goblin': {
                    'Warrior': "Born amidst the jumbled tapestry of the Goblin junkyards, you quickly learned that "
                               "one person's trash can be another's deadly weapon. As a Warrior, you're no stranger "
                               "to the roar of battle. With scrap metal armor and rusted blade, you're ready to prove "
                               "that even the underdogs have their day.",
                    'Mage': "Raised amidst the wreckage of the Goblin domain, you saw magic in the forgotten relics "
                            "and discarded artifacts. As a Mage, you weave spells with a unique flair, turning "
                            "discarded junk into arcane wonders. The battlefield will be your canvas and magic, your "
                            "brush.",
                    'Rogue': "In the sprawling chaos of the Goblin shanties, you learned that not all treasures "
                             "are gold and gems. As a Rogue, you honed your craft in the shadowed alleys, becoming a "
                             "master of stealth and deception. To you, every locked chest or guarded vault is simply "
                             "an invitation.",
                }
            }

    async def generate_embed(self, class_key):
        class_details = self.classes[class_key]
        embed = discord.Embed(title=class_details['header'], description=class_details['description'],
                              color=class_details['color'])
        embed.set_image(url=class_details['image_url'])
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_class_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_class_index = (self.current_class_index - 1) % len(self.class_keys)
        await interaction.response.edit_message(
            embed=await self.generate_embed(self.class_keys[self.current_class_index]))

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_class_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_class_index = (self.current_class_index + 1) % len(self.class_keys)
        await interaction.response.edit_message(
            embed=await self.generate_embed(self.class_keys[self.current_class_index]))

    @discord.ui.button(emoji="<:Select:1108065587587993650>", style=discord.ButtonStyle.primary)
    async def select_class_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        try:
            selected_class = self.class_keys[self.current_class_index]
            selected_class_stats = self.classes[selected_class]['stats']

            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT player_race FROM player_races WHERE player_id = %s AND server_id = %s
                    """, (self.ctx.author.id, self.ctx.guild.id))
                    data = await cur.fetchone()
                    if data is not None:
                        player_race = data[0]

            if player_race in self.classes[selected_class]['race_bonuses']:
                for stat, bonus in self.classes[selected_class]['race_bonuses'][player_race].items():
                    selected_class_stats[stat] += bonus

            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        INSERT INTO player_classes (server_id, player_id, class_name, image_url, strength, intellect, agility, constitution, player_level, remaining_stat_points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.ctx.guild.id,
                        self.ctx.author.id,
                        selected_class,
                        self.classes[selected_class]['image_url'],
                        selected_class_stats['strength'],
                        selected_class_stats['intellect'],
                        selected_class_stats['agility'],
                        selected_class_stats['constitution'],
                        1,
                        0
                    ))
                    await conn.commit()
            embed = discord.Embed(
                title=f"{player_race} {selected_class}",
                description=self.class_descriptions[player_race][selected_class],
                color=discord.Color.dark_gold()
            )
            embed.set_thumbnail(url=self.classes[selected_class]['image_url'])
            embed.set_footer(
                text=f"Strength: {selected_class_stats['strength']} | Intellect: {selected_class_stats['intellect']} "
                     f"| Agility: {selected_class_stats['agility']} | Constitution: {selected_class_stats['constitution']}")

            await self.ctx.send(embed=embed)
            await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 3)
            await _continuec(self.ctx)

        except Exception as e:
            print(f"Error while selecting class: {e}")
            await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 2)
async def select_class(ctx):
    bot = ctx.bot
    guild_idz = 1104234202624426038
    guildz = bot.get_guild(guild_idz)

    race_bonuses = {
        'Elf': {
            'agility': 3
        },
        'Gnome': {
            'intellect': 3
        },
        'Dwarf': {
            'constitution': 3
        },
        'Orc': {
            'strength': 3
        },
        'Goblin': {
            'intellect': 1,
            'agility': 2
        },
        'Human': {
            'intellect': 1,
            'agility': 1,
            'constitution': 1,
            'strength': 1
        },
    }
    classes = {
        'Warrior': {
            'image_url': "https://imagizer.imageshack.com/img924/7526/uaaf4Q.png",
            'description': '- Mighty Blow: 1% chance per STR point to double the attack damage.\n- Iron Skin: Decrease incoming damage by 0.2% per CON point.\n- Frenzy: 1% chance per STR point to counterattack if attacked twice consecutively.',
            'header': 'Warrior',
            'color': 0xFF0000,
            'stats': {
                'strength': 5,
                'intellect': 1,
                'agility': 2,
                'constitution': 2
            },
            'race_restrictions': ['Human', 'Gnome', 'Goblin', 'Elf', 'Dwarf', 'Orc'],
            'race_bonuses': race_bonuses
        },
        'Mage': {
            'image_url': "https://imagizer.imageshack.com/img923/9729/LjsxJD.png",
            'description': '- Arcane Infusion: 0.3% chance per INT point to grant an ally card a defensive bonus for the next incoming attack.\n- Spell Echo: 0.4% chance per INT point to trigger the last spell used again without additional cost.\n- Mana Surge: After successfully casting a spell, gain a 0.1% chance per INT point to increase the effectiveness of the next spell.',
            'header': 'Mage ',
            'color': 0x4B0082,
            'stats': {
                'strength': 1,
                'intellect': 5,
                'agility': 2,
                'constitution': 2
            },
            'race_restrictions': ['Human', 'Gnome', 'Goblin', 'Elf', 'Dwarf', 'Orc'],
            'race_bonuses': race_bonuses
        },
        'Rogue': {
            'image_url': "https://imagizer.imageshack.com/img922/4316/awpyP3.png",
            'description': '- Shadowstep: 0.5% chance per AGI point to evade an incoming attack completely.\n- Quick Strike: 0.3% chance per AGI point to preemptively interrupt an opponent\'s action.\n- Silent Assassin: If an opponent\'s defense is significantly lower, there\'s a 1% chance per AGI to instantly remove the opponent\'s card.',
            'header': 'Rogue',
            'color': 0x008000,  # Green
            'stats': {
                'strength': 1,
                'intellect': 2,
                'agility': 5,
                'constitution': 2
            },
            'race_restrictions': ['Human', 'Gnome', 'Goblin', 'Elf', 'Dwarf', 'Orc'],
            'race_bonuses': race_bonuses
        },
    }

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT class_name FROM player_classes WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                await ctx.send("You've already selected a class.")
                await update_player_stage(ctx.guild.id, ctx.author.id, 3)
                return

            await cur.execute("""
                SELECT player_race FROM player_races WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                player_race = data[0]

    # Filter classes based on player's race
    available_classes = {key: value for key, value in classes.items() if player_race in value['race_restrictions']}
    class_keys = list(available_classes.keys())

    view = ClassSelectView(ctx, classes, class_keys, pool, ctx.author)
    message = await ctx.send(embed=await view.generate_embed(class_keys[0]), view=view)
class JobSelectView(discord.ui.View):
    def __init__(self, ctx, jobs, job_keys, pool, command_user):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.jobs = jobs
        self.job_keys = job_keys
        self.current_job_index = 0
        self.pool = pool
        self.command_user = command_user

    async def generate_embed(self, job_key):
        job_details = self.jobs[job_key]
        embed = discord.Embed(title=job_details['header'], description=job_details['description'],
                              color=job_details['color'])
        embed.set_image(url=job_details['image_url'])
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_job_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_job_index = (self.current_job_index - 1) % len(self.job_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.job_keys[self.current_job_index]))

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_job_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_job_index = (self.current_job_index + 1) % len(self.job_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.job_keys[self.current_job_index]))

    @discord.ui.button(emoji="<:Select:1108065587587993650>", style=discord.ButtonStyle.primary)
    async def select_job_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        selected_job = self.job_keys[self.current_job_index]
        selected_job_stats = self.jobs[selected_job]['stats']
        enhanced_stat = self.jobs[selected_job]['enhanced_stat']

        # Get the player's race and enhance the job's relevant stat
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT player_race FROM player_races WHERE player_id = %s AND server_id = %s
                """, (self.ctx.author.id, self.ctx.guild.id))
                data = await cur.fetchone()
                if data is not None:
                    player_race = data[0]

        if player_race in self.jobs[selected_job]['race_proficiency']:
            for stat, proficiency in self.jobs[selected_job]['race_proficiency'][player_race].items():
                selected_job_stats[stat] += proficiency

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    # Updating player's job
                    await cur.execute("""
                        INSERT INTO player_jobs (server_id, player_id, job_name, image_url, Proficiency, Stamina, Focus, job_level, remaining_stat_points)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        self.ctx.guild.id,
                        self.ctx.author.id,
                        selected_job,
                        self.jobs[selected_job]['image_url'],
                        selected_job_stats['proficiency'],
                        selected_job_stats['stamina'],
                        selected_job_stats['focus'],
                        1,
                        5
                    ))

                    # Enhancing player's stat in player_classes table
                    await cur.execute(f"""
                        UPDATE player_classes
                        SET {enhanced_stat} = {enhanced_stat} + 2
                        WHERE player_id = %s AND server_id = %s
                    """, (self.ctx.author.id, self.ctx.guild.id))

                    await conn.commit()
                    await self.ctx.send(f"You have selected {selected_job}")
                    await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 5)
                    await _continuec(self.ctx)
                    self.stop()
                except:
                    await update_player_stage(self.ctx.guild.id, self.ctx.author.id, 4)
                    self.stop()
async def select_job(ctx):
    bot = ctx.bot
    guild_idz = 1104234202624426038
    guildz = bot.get_guild(guild_idz)

    race_proficiency = {
        'Elf': {
            'focus': 3
        },
        'Gnome': {
            'proficiency': 3
        },
        'Dwarf': {
            'stamina': 3
        },
        'Orc': {
            'stamina': 3
        },
        'Goblin': {
            'focus': 1,
            'stamina': 2
        },
        'Human': {
            'proficiency': 1,
            'stamina': 1,
            'focus': 1
        },
    }

    jobs = {
        'Miner': {
            'image_url': "https://imagizer.imageshack.com/img924/961/MYxUj9.png",
            'description': '- Rock Splitter: With every swing, there is a small chance based on STR to extract double the'
                           ' ores and gems.\n- Endurance: Increases stamina, allowing for prolonged mining sessions.\n- '
                           'Stone Skin: Miners are tough, granting them a minor boost to STR.',
            'header': 'Miner',
            'color': 0xFFD700,
            'stats': {
                'proficiency': 1,
                'stamina': 5,
                'focus': 1
            },
            'race_restrictions': ['Human', 'Gnome', 'Dwarf', 'Orc', 'Elf', 'Goblin'],
            'race_proficiency': race_proficiency,
            'enhanced_stat': 'strength'
        },
        'Woodsman': {
            'image_url': "https://imagizer.imageshack.com/img922/8554/Szqry5.png",
            'description': '- Nature\'s Bounty: Has a small chance based on AGI to gather double the woods and plants'
                           '.\n- Woodland Wisdom: Increases focus, leading to better identification of useful resources'
                           '.\n- Agile Harvest: Woodsmen are agile, thus a minor AGI boost is granted.',
            'header': 'Woodsman',
            'color': 0x006400,
            'stats': {
                'proficiency': 1,
                'stamina': 1,
                'focus': 5
            },
            'race_restrictions': ['Human', 'Gnome', 'Dwarf', 'Orc', 'Elf', 'Goblin'],
            'race_proficiency': race_proficiency,
            'enhanced_stat': 'agility'
        },
        'Archaeologist': {
            'image_url': "https://imagizer.imageshack.com/img922/7610/ELUUOL.png",
            'description': '- Ancient Knowledge: Has a small chance based on INT to uncover additional parchments and '
                           'relics.\n- Studious Mind: Increases proficiency, allowing a better understanding of historical'
                           ' items.\n- Scholar\'s Insight: Archaeologists are smart, thus they are given a minor '
                           'boost to INT.',
            'header': 'Archaeologist',
            'color': 0x8B4513,
            'stats': {
                'proficiency': 5,
                'stamina': 1,
                'focus': 1
            },
            'race_restrictions': ['Human', 'Gnome', 'Dwarf', 'Orc', 'Elf', 'Goblin'],
            'race_proficiency': race_proficiency,
            'enhanced_stat': 'intellect'
        },
        'Farmer': {
            'image_url': "https://imagizer.imageshack.com/img923/9650/50YqQz.png",
            'description': '- Bountiful Harvest: Has a small chance based on CON to collect additional crops and animal '
                           'products.\n- Agrarian Wisdom: Increases proficiency, allowing better crop and animal '
                           'management.\n- Hardy Constitution: Farmers are sturdy, so they have a minor boost to CON.',
            'header': 'Farmer',
            'color': 0x8B4513,
            'stats': {
                'proficiency': 2,
                'stamina': 3,
                'focus': 2
            },
            'race_restrictions': ['Human', 'Gnome', 'Dwarf', 'Orc', 'Elf', 'Goblin'],
            'race_proficiency': race_proficiency,
            'enhanced_stat': 'constitution'
        },
    }
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT job_name FROM player_jobs WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                await ctx.send("You've already selected a job.")
                await update_player_stage(ctx.guild.id, ctx.author.id, 5)
                return

            await cur.execute("""
                SELECT player_race FROM player_races WHERE player_id = %s AND server_id = %s
            """, (ctx.author.id, ctx.guild.id))
            data = await cur.fetchone()
            if data is not None:
                player_race = data[0]

    available_jobs = {key: value for key, value in jobs.items() if player_race in value['race_restrictions']}
    job_keys = list(available_jobs.keys())

    view = JobSelectView(ctx, jobs, job_keys, pool, ctx.author)
    message = await ctx.send(embed=await view.generate_embed(job_keys[0]), view=view)
class StatChallengeView(discord.ui.View):
    def __init__(self, ctx, stats, command_user):
        super().__init__()
        self.server_id = ctx.guild.id
        self.player_id = ctx.author.id
        self.ctx = ctx
        self.stats = stats
        self.current_stat_index = 0
        self.stat_keys = list(stats.keys())
        self.command_user = command_user
        self.stat_flavors = {
                'strength': {
                    'flavor_text': "Eyeing a formidable boulder near the entrance, you opt to demonstrate your raw strength. The boulder, rough and weathered, stands as an embodiment of the city's rugged nature.",
                    'image_url': "https://imagizer.imageshack.com/img923/3789/kN5cgn.png",
                    'failure_text': "Summoning all your might, you attempt to lift the stone. The boulder seems to scoff at your effort, refusing to yield. A muffled chuckle escapes from the guards as your cheeks flush with exertion.",
                    'success_text': "With a calmness that belies the task, you wrap your arms around the boulder. With an effortless heave, the boulder rises. The guards' mockery fades, replaced by surprised respect. A grudging nod from them attests to your impressive strength."
                },
                'intellect': {
                    'flavor_text': "Deciding to employ your intellect, you prepare to dazzle the guards with an array of arcane energy. Magic pulses at your fingertips, unseen but potent.",
                    'image_url': "https://imagizer.imageshack.com/img923/4962/1Ppad6.png",
                    'failure_text': "Your hands weave in the air, conjuring an incantation. A weak sputter of sparks is all that answers, dissipating in the air almost immediately. The guards raise their eyebrows, a silent question of your boasted capabilities.",
                    'success_text': "Your hands move deftly, channelling the arcane power that seethes within you. With a final flourish, you send forth a spectacular burst of energy that dances in the air, forming intricate glyphs of power. The guards look on in awe, their doubts silenced."
                },
                'agility': {
                    'flavor_text': "You choose to demonstrate your agility, turning your attention to an impromptu obstacle course near the entrance. It promises a challenging sequence of acrobatics.",
                    'image_url': "https://imagizer.imageshack.com/img922/8012/za1Ayk.png",
                    'failure_text': "Taking a deep breath, you launch into the course. A misjudged leap, however, sends you stumbling over an obstacle. The guards' amusement is clear, their laughter echoing off the stone walls.",
                    'success_text': "With a fluid grace, you navigate the course. Flips, slides and nimble footwork carry you through, culminating in a flawless landing. The guards' grins fade into impressed nods, acknowledging your remarkable agility."
                },
                'constitution': {
                    'flavor_text': "To prove your endurance, you decide to withstand a barrage of magical strikes. The air crackles with anticipation as you square your shoulders and meet the guards' gaze.",
                    'image_url': "https://imagizer.imageshack.com/img924/3980/cjxMZX.png",
                    'failure_text': "Bracing yourself, you try to withstand the flurry of magic. Each strike elicits a wince, your determination wavering. The guards shake their heads, their silent judgment falling upon you like a weight.",
                    'success_text': "Even as the magical strikes rain upon you, you stand resolute. Each impact glows harmlessly off you, your endurance unwavering. The onslaught ends, and yet, you stand. The guards exchange impressed looks before giving approving nods, acknowledging your exceptional fortitude."
                }
            }

    async def generate_embed(self, stat_key):
        stat_value = self.stats[stat_key]
        flavor_text = self.stat_flavors[stat_key]['flavor_text']
        image_url = self.stat_flavors[stat_key]['image_url']

        embed = discord.Embed(title=f"Challenge: {stat_key}", description=f"{flavor_text}", color=0x00ff00)
        embed.set_footer(text=f"Stat Value: {stat_value}")

        embed.set_image(url=image_url)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_stat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_stat_index = (self.current_stat_index - 1) % len(self.stat_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.stat_keys[self.current_stat_index]))

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_stat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        self.current_stat_index = (self.current_stat_index + 1) % len(self.stat_keys)
        await interaction.response.edit_message(embed=await self.generate_embed(self.stat_keys[self.current_stat_index]))

    @discord.ui.button(emoji="<:Select:1108065587587993650>", style=discord.ButtonStyle.primary)
    async def select_stat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return
        selected_stat = self.stat_keys[self.current_stat_index]
        selected_stat_value = self.stats[selected_stat]

        # Check if stat value is high enough
        if selected_stat_value >= 5:
            success_text = self.stat_flavors[selected_stat]['success_text']
            embed = discord.Embed(title=f"Success! {selected_stat} challenge", description=success_text, color=0x00ff00)
            embed.set_footer(text=f"Stat Value: {selected_stat_value}")
            embed.set_thumbnail(url=self.stat_flavors[selected_stat]['image_url'])
            await interaction.response.send_message(embed=embed)
            await update_player_stage(self.server_id, self.player_id, 4)
            await _continuec(self.ctx)
        else:
            await update_player_stage(self.server_id, self.player_id, 3)
            failure_text = self.stat_flavors[selected_stat]['failure_text']
            embed = discord.Embed(title=f"Failure! {selected_stat} challenge", description=failure_text, color=0xff0000)
            embed.set_footer(text=f"Stat Value: {selected_stat_value}")
            embed.set_thumbnail(url=self.stat_flavors[selected_stat]['image_url'])
            await interaction.response.send_message(embed=embed)
            await _continuec(self.ctx)
async def challenge_stat(ctx, stats):
    view = StatChallengeView(ctx, stats, ctx.author)
    initial_stat_key = view.stat_keys[view.current_stat_index]
    initial_embed = await view.generate_embed(initial_stat_key)
    await ctx.send(embed=initial_embed, view=view)
async def update_player_stage(server_id, player_id, new_stage):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                UPDATE player_campaign_progress
                SET player_stage = %s
                WHERE server_id = %s AND player_id = %s AND completed = 0
            """, (new_stage, server_id, player_id))
            await conn.commit()
async def start_player_quest(ctx, server_id, player_id, bot):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT quest_id, player_stage
                FROM player_campaign_progress
                WHERE server_id = %s AND player_id = %s AND completed = 0
            """, (server_id, player_id))
            quest_result = await cursor.fetchone()
            if quest_result is None:
                await ctx.send("You don't have any active quests.")
                return
            quest_id, player_stage = quest_result

            # Call the function for this quest
            handler = quest_handlers.get(quest_id)
            if handler is None:
                await ctx.send("An error occurred. The handler for your quest could not be found.")
                return

            await handler(ctx, server_id, player_id, bot, player_stage)
async def check_available_quests(ctx, server_id, player_id, bot):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Fetch the player's race
            await cursor.execute("""
                SELECT player_race
                FROM player_races
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id))
            player_race_result = await cursor.fetchone()
            player_race = player_race_result[0] if player_race_result is not None else 'any'

            await cursor.execute("""
                SELECT cq.id, cq.name, cq.total_stages, cq.image_url, cq.description, cq.reward
                FROM campaign_quests cq
                WHERE cq.race IN ('any', %s)
                ORDER BY cq.name ASC
            """, (player_race,))

            quests = await cursor.fetchall()

            if not quests:
                await ctx.send(f"No quests are available for your race.")
                return

            current_quest_index = 0

            def generate_embed(quest):
                quest_id, name, total_stages, image_url, description, reward = quest
                embed = discord.Embed(title=name, description=description)
                embed.set_image(url=image_url)
                footer_text = f'Total Stages: {total_stages} | '
                footer_text +=f'Quest {current_quest_index + 1} of {len(quests)}'
                embed.set_footer(text=footer_text)
                return embed

            message = await ctx.send(embed=generate_embed(quests[current_quest_index]))

            # The same emoji guild and definitions as in your check_owned_cards function
            guild_idz = 1104234202624426038
            emoji_Rarrow = 1106624275034677360
            emoji_Larrow = 1106624302268297286
            emoji_Enlist = 1106633767684153405
            guildz = bot.get_guild(guild_idz)
            Larrow = discord.utils.get(guildz.emojis, id=emoji_Larrow)
            Rarrow = discord.utils.get(guildz.emojis, id=emoji_Rarrow)
            Enlist = discord.utils.get(guildz.emojis, id=emoji_Enlist)

            await message.add_reaction(f"{Larrow}")
            await message.add_reaction(f"{Rarrow}")
            await message.add_reaction(f"{Enlist}")

            def check(reaction, user):
                return user == ctx.author and reaction.emoji.id in [emoji_Larrow, emoji_Rarrow, emoji_Enlist]

            while True:
                try:
                    reaction, user = await ctx.bot.wait_for("reaction_add", timeout=60, check=check)

                    if reaction.emoji.id == emoji_Rarrow:
                        current_quest_index = (current_quest_index + 1) % len(quests)
                    elif reaction.emoji.id == emoji_Larrow:
                        current_quest_index = (current_quest_index - 1) % len(quests)
                    elif reaction.emoji.id == emoji_Enlist:
                        selected_quest = quests[current_quest_index]
                        # Start the selected quest with stage 1
                        await cursor.execute("""
                            INSERT INTO player_campaign_progress (server_id, player_id, quest_id, player_stage)
                            VALUES (%s, %s, %s, 1)
                        """, (server_id, player_id, selected_quest[0]))
                        await ctx.send(f"You have selected the quest '{selected_quest[1]}'. Good luck!")
                        break

                    await message.edit(embed=generate_embed(quests[current_quest_index]))
                    await message.remove_reaction(reaction, user)
                except asyncio.TimeoutError:
                    await message.clear_reactions()
                    break
async def The_Guilds_Invitation(ctx, server_id, player_id, bot, player_stage):
    embed = discord.Embed(title="The Invitation", color=0x6E6E6E)

    if player_stage == 1:
        embed.description = (
            "Beneath the dawn light, you stand at the gates of Syloria, the thriving heart of Eldoria. "
            "The city resonates with the diverse harmony of races each contributing to the city\'s vibrant "
            "pulse.Before you, the grand Adventure Guild Hall invites all to seek their destiny. As you "
            "prepare to introduce yourself, you sense the stirring of an epic saga. Welcome, adventurer. "
            "Today, you begin your story in the annals of Eldoria\'s history.")
        await ctx.send(embed=embed)
        await select_race(ctx)

    elif player_stage == 2:
        await select_class(ctx)

    elif player_stage == 3:
        embed.description = (
            "As you approach the grand entrance of the Adventure Guild Hall, an imposing stone structure "
            "with towering arched doors, a shiver of anticipation stirs within you. A pair of hardy, armored"
            " guards, a Dwarf and a Half-Orc, scrutinize you with a discerning gaze, their silence echoing"
            " a sentiment that needs no words. As you step closer, it's clear they're silently conveying,"
            " \'Show us what you're made of.\'")
        await ctx.send(embed=embed)

        player_stats = await get_player_stats(player_id, server_id)

        await challenge_stat(ctx, player_stats)

    elif player_stage == 4:
        embed.description = (
            "Crossing the threshold into the Adventure Guild Hall, you meet the Guild Master, a man less "
            "the image of heroic legend and more the embodiment of clerical tedium. Stacks of parchment "
            "surround him, and he shoves a form towards you – the Adventurer's Application – surprisingly "
            "mundane in the heart of Eldoria's grandeur.\'Application fee is a fifty florins,\' he "
            "murmurs, barely glancing up from his work. You choke on surprise; you don\'t have fifty "
            "florins. The harsh reality of bureaucracy hits you. He simply shrugs and "
            "turns you away, leaving you with the task of earning your place here. Despite this setback, a "
            "sense of determination kindles within you; the grandeur of your adventure, it seems, will "
            "begin with some humble toil.")
        embed.set_image(url="https://imagizer.imageshack.com/img923/702/415TNX.png")
        await ctx.send(embed=embed)
        await select_job(ctx)

    elif player_stage == 5:
        embed.description = (
            "Taking the weight of the Guild Master's words in stride, you step forth into the bustling "
            "streets of Syloria. A newfound determination kindles within your heart as you prepare to "
            "face your first hurdle. Come back with 10 florins. \n \n"
            "***$work***    Gather resources of your chosen job \n"
            "***$market***   See the current market\n"
            "***$sell*** (itemname)    Sell a specific item\n"
            "***$buy*** (itemname)    Buy a specific item\n"
            "***$sellall***   Quickly sell everything\n")
        await ctx.send(embed=embed)
        await update_player_stage(server_id, player_id, 6)

    elif player_stage == 6:
        embed.description = (
            "You return to the Adventure Guild Hall, your pockets slightly heavier with the modest earnings from your recent toil. "
            "The grand edifice, which once seemed so daunting, now feels a bit more welcoming. The experience of working in Syloria "
            "has started to chip away at your initial apprehension. You can't help but feel a sense of pride; you've taken the "
            "first step on your journey, however small it may be. "
            "As you approach the desk of the Guild Master once again, the bureaucratic figure raises an eyebrow, acknowledging your "
            "return. 'Ready to pay the fee?' he says smirkingly.")
        await ctx.send(embed=embed)
        await review_contract(ctx, server_id, player_id)


    elif player_stage == 7:
        embed.description = (
            "Having traded your modest earnings for the Guild's stamped approval, the spark of anticipation flares within you. As the "
            "Guild Master's quill records your name into the annals of Eldoria's adventurers, he pauses, setting down the heavy "
            "quill with a contemplative expression. A mirthless grin cracks his stoic facade as he ushers you into the reality of your "
            "new role.\n\n"
            "'It seems fate has a flair for the dramatic, new blood,' he begins, his eyes carrying the weight of centuries. 'A tempest "
            "stirs among the pillars of our fair Eldoria. The Ferocious Pact, their orc and goblin banners flapping wildly, gnash their "
            "teeth at the stoic Noble Coalition, whose elven and human soldiers eye them with palpable disdain. Meanwhile, the Stout "
            "Alliance, our diligent dwarves and gnomes, churn with unease, their forges glowing with anticipation. The discord among these "
            "factions frays the edges of our harmony.'\n\n"
            "His voice drops, 'Your first task lies not in battle with a fire-breathing dragon nor in unearthing lost treasures... No, "
            "it's a test of diplomacy. I urge you to seek your kin, your race's representative, and lend your voice to soften their stance. \n\n"
        )
        embed.set_thumbnail(url="https://imagizer.imageshack.com/img922/8813/bBx7zL.png")
        await ctx.send(embed=embed)
        await approach_race_representative(ctx, player_id, server_id)

    elif player_stage == 8:
        embed.description = (
            'You can now recruit allies with ***$roll***, and build with ***$build***. \n\n End for now')
        embed.set_thumbnail(url="https://imagizer.imageshack.com/img922/8813/bBx7zL.png")
        await ctx.send(embed=embed)

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                        UPDATE player_races
                        SET racial_3 = 1
                        WHERE server_id = %s AND player_id = %s
                    """, (server_id, player_id))

quest_handlers = {
    1: The_Guilds_Invitation,
}


#Items
@bot.command(name="id", brief='Identify items')
async def _shop(ctx):
    bot = ctx.bot
    player_id = ctx.author.id
    server_id = ctx.guild.id
    await Database.identify_item(ctx, server_id, player_id, bot, pool)

#All Stat Stuff
class PlayerStatsView(discord.ui.View):
    def __init__(self, ctx, target_user):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.target_user = target_user
        self.current_class_index = 0
        self.current_view = 'stats'

    async def generate_image(self, stats_dict, feats, class_name, race_name, image_url, job_name, florins):
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        d = ImageDraw.Draw(img)
        stats_font = ImageFont.truetype("arial.ttf", 140)
        feats_font = ImageFont.truetype("arial.ttf", 75)
        class_race_font = ImageFont.truetype("arial.ttf", 120)
        job_font = ImageFont.truetype("arial.ttf", 60)
        gold_font = ImageFont.truetype("arial.ttf", 80)

        positions = {
            "Str": (240, 500, stats_font),
            "Int": (240, 850, stats_font),
            "Agi": (240, 680, stats_font),
            "Con": (240, 1025, stats_font),
            "ClassRace": (10, 10, class_race_font),
            "Job": (1722, 49, job_font),
            "Florins": (1722, 188, gold_font),
        }

        feat_positions = [
            (1665, 920, feats_font),
            (1665, 1010, feats_font),
            (1665, 1110, feats_font),
        ]
        for key, value in stats_dict.items():
            x, y, font = positions[key]
            d.text((x, y), str(value), fill="black", font=font)

        for i, feat in enumerate(feats):
            x, y, font = feat_positions[i]
            d.text((x, y), feat, fill="black", font=font)

        x, y, font = positions["ClassRace"]
        d.text((x, y), f"{race_name} {class_name}", fill="black", font=font)

        x, y, font = positions["Job"]
        d.text((x, y), job_name, fill="black", font=font)

        x, y, font = positions["Florins"]
        d.text((x, y), str(florins), fill="black", font=font)

        img.save(f"{self.ctx.author.id}_stats.png")

    async def generate_embed(self):
        server_id = self.ctx.guild.id
        player_id = self.target_user.id
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if self.current_view == 'stats':
                    await cur.execute("""
                        SELECT pc.class_name, pc.image_url, pc.strength, pc.intellect, pc.agility, pc.constitution, pc.player_level, pc.remaining_stat_points, 
                        pj.job_name, pr.player_race, uf.florins,
                        pi.strength as item_strength, pi.intellect as item_intellect, pi.agility as item_agility, pi.constitution as item_constitution,
                        pf.Stealth, pf.Acrobatics, pf.Deception, pf.Insight, pf.Intimidation, pf.Investigation, pf.Medicine, pf.Religion, pf.Persuasion, pf.Performance, pf.Perception, pf.Arcana
                        FROM player_classes pc
                        LEFT JOIN player_jobs pj ON pc.player_id = pj.player_id AND pc.server_id = pj.server_id
                        LEFT JOIN player_races pr ON pc.player_id = pr.player_id AND pc.server_id = pr.server_id
                        LEFT JOIN user_florins uf ON pc.player_id = uf.user_id AND pc.server_id = uf.server_id
                        LEFT JOIN player_items pi ON pc.player_id = pi.player_id AND pc.server_id = pi.server_id
                        LEFT JOIN player_feats pf ON pc.player_id = pf.player_id AND pc.server_id = pf.server_id
                        WHERE pc.player_id = %s AND pc.server_id = %s
                    """, (player_id, server_id))
                    data = await cur.fetchone()

                    feats = [feat for feat, value in data.items() if value == 1 and feat in (
                    'Stealth', 'Acrobatics', 'Deception', 'Insight', 'Intimidation', 'Investigation', 'Medicine',
                    'Religion', 'Persuasion', 'Performance', 'Perception', 'Arcana')] if data else []

                    if data is not None:
                        image_url = 'https://imagizer.imageshack.com/img924/3148/bA1aO9.png'
                        strength = int(data['strength']) + int(data['item_strength']) if data[
                                                                                             'item_strength'] is not None else int(
                            data['strength'])
                        intellect = int(data['intellect']) + int(data['item_intellect']) if data[
                                                                                                'item_intellect'] is not None else int(
                            data['intellect'])
                        agility = int(data['agility']) + int(data['item_agility']) if data[
                                                                                          'item_agility'] is not None else int(
                            data['agility'])
                        constitution = int(data['constitution']) + int(data['item_constitution']) if data[
                                                                                                         'item_constitution'] is not None else int(
                            data['constitution'])

                        stats_dict = {
                            "Str": strength,
                            "Int": intellect,
                            "Agi": agility,
                            "Con": constitution,
                        }

                    await self.generate_image(stats_dict, feats, data['class_name'], data['player_race'],
                                              'https://imagizer.imageshack.com/img924/3148/bA1aO9.png',
                                              data['job_name'], data['florins'])

                elif self.current_view == 'items':
                    await cur.execute("""
                        SELECT g.slot, i.player_item_id, i.name, i.curse_1, i.enchantment_1
                        FROM player_gear g
                        LEFT JOIN player_items i ON g.item_id = i.player_item_id
                        WHERE g.server_id = %s AND g.player_id = %s
                    """, (server_id, player_id,))
                    gear_data = await cur.fetchall()

                    if not gear_data:
                        return discord.Embed(title="No items equipped", color=0xff0000)

                    slot_to_item_name = {item['slot']: ' '.join(filter(None, [item['curse_1'], item['name'],
                                                                              f"of {item['enchantment_1']}" if item[
                                                                                  'enchantment_1'] else None])) for item
                                         in gear_data}

                    embed = discord.Embed(title=f"{self.target_user.name}'s Equipment", color=0x3498db)
                    for slot, item_name in slot_to_item_name.items():
                        embed.add_field(name=slot, value=item_name, inline=False)

                    return embed

    async def show_initial_embed(self):
        self.current_view = 'stats'
        await self.generate_embed()
        await self.ctx.send(file=discord.File(f"{self.ctx.author.id}_stats.png"), view=self)

@bot.command(name="stats", brief='Show your stats')
async def player_info(ctx, user: discord.Member = None):
    if user is None:
        user = ctx.author

    view = PlayerStatsView(ctx, user)
    await view.show_initial_embed()
async def get_player_stats(player_id, server_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT class_name, strength, intellect, agility, constitution 
                FROM player_classes 
                WHERE player_id = %s AND server_id = %s
            """, (player_id, server_id))
            data = await cur.fetchone()

            # Initialize item stats to zero
            item_strength = item_intellect = item_agility = item_constitution = 0

            # Fetch gear data
            await cur.execute("""
                SELECT * 
                FROM player_gear
                WHERE player_id = %s AND server_id = %s
            """, (player_id, server_id))
            gear_data = await cur.fetchone()

            # If player has gear
            if gear_data is not None:
                for slot, item_id in gear_data.items():
                    if item_id is not None:
                        await cur.execute("""
                            SELECT strength, intellect, agility, constitution 
                            FROM player_items
                            WHERE player_item_id = %s
                        """, (item_id,))
                        item_data = await cur.fetchone()

                        if item_data is not None:
                            item_strength += item_data['strength'] or 0
                            item_intellect += item_data['intellect'] or 0
                            item_agility += item_data['agility'] or 0
                            item_constitution += item_data['constitution'] or 0

            player_stats = {
                'strength': int(data['strength']) + item_strength,
                'intellect': int(data['intellect']) + item_intellect,
                'agility': int(data['agility']) + item_agility,
                'constitution': int(data['constitution']) + item_constitution
            }

            return player_stats




            view = StatChallengeView(ctx, player_stats, ctx.author)
            await view.show_initial_embed()
async def get_player_statsQ(player_id, server_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT class_name, strength, intellect, agility, constitution 
                FROM player_classes 
                WHERE player_id = %s AND server_id = %s
            """, (player_id, server_id))
            data = await cur.fetchone()

            # Initialize item stats to zero
            item_strength = item_intellect = item_agility = item_constitution = 0

            # Fetch gear data
            await cur.execute("""
                SELECT * 
                FROM player_gear
                WHERE player_id = %s AND server_id = %s
            """, (player_id, server_id))
            gear_data = await cur.fetchone()

            # If player has gear
            if gear_data is not None:
                for slot, item_id in gear_data.items():
                    if item_id is not None:
                        await cur.execute("""
                            SELECT strength, intellect, agility, constitution 
                            FROM player_items
                            WHERE player_item_id = %s
                        """, (item_id,))
                        item_data = await cur.fetchone()

                        if item_data is not None:
                            item_strength += item_data['strength'] or 0
                            item_intellect += item_data['intellect'] or 0
                            item_agility += item_data['agility'] or 0
                            item_constitution += item_data['constitution'] or 0

            player_stats = {
                'strength': int(data['strength']) + item_strength,
                'intellect': int(data['intellect']) + item_intellect,
                'agility': int(data['agility']) + item_agility,
                'constitution': int(data['constitution']) + item_constitution
            }

            return player_stats














#Side Questing Functions
player_info_cache = {}

async def cache_player_info(player_id, server_id):
    # Make a unique identifier for each player and server combination
    unique_id = f"{player_id}_{server_id}"

    if unique_id in player_info_cache:
        del player_info_cache[unique_id]

    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT pc.class_name, pc.image_url, pc.strength, pc.intellect, pc.agility, pc.constitution, 
                pc.player_level, pc.remaining_stat_points, pj.job_name, pr.player_race, uf.florins,
                pi.strength as item_strength, pi.intellect as item_intellect, pi.agility as item_agility, 
                pi.constitution as item_constitution,
                pf.Stealth, pf.Acrobatics, pf.Deception, pf.Insight, pf.Intimidation, pf.Investigation, 
                pf.Medicine, pf.Religion, pf.Persuasion, pf.Performance, pf.Perception, pf.Arcana
                FROM player_classes pc
                LEFT JOIN player_jobs pj ON pc.player_id = pj.player_id AND pc.server_id = pj.server_id
                LEFT JOIN player_races pr ON pc.player_id = pr.player_id AND pc.server_id = pr.server_id
                LEFT JOIN user_florins uf ON pc.player_id = uf.user_id AND pc.server_id = uf.server_id
                LEFT JOIN player_items pi ON pc.player_id = pi.player_id AND pc.server_id = pi.server_id
                LEFT JOIN player_feats pf ON pc.player_id = pf.player_id AND pc.server_id = pf.server_id
                WHERE pc.player_id = %s AND pc.server_id = %s
            """, (player_id, server_id))

            data = await cur.fetchone()
            feats = [feat for feat, value in data.items() if value == 1 and feat in (
                'Stealth', 'Acrobatics', 'Deception', 'Insight', 'Intimidation', 'Investigation',
                'Medicine', 'Religion', 'Persuasion', 'Performance', 'Perception', 'Arcana'
            )] if data else []

            if data is not None:
                image_url = 'https://imagizer.imageshack.com/img924/3148/bA1aO9.png'
                strength = int(data['strength']) + int(data['item_strength']) if data[
                                                                                     'item_strength'] is not None else int(
                    data['strength'])
                intellect = int(data['intellect']) + int(data['item_intellect']) if data[
                                                                                        'item_intellect'] is not None else int(
                    data['intellect'])
                agility = int(data['agility']) + int(data['item_agility']) if data['item_agility'] is not None else int(
                    data['agility'])
                constitution = int(data['constitution']) + int(data['item_constitution']) if data[
                                                                                                 'item_constitution'] is not None else int(
                    data['constitution'])

                stats_dict = {
                    "strength": strength,
                    "intellect": intellect,
                    "agility": agility,
                    "constitution": constitution,
                }

                health_multipliers = {
                    'mage': 3,
                    'rogue': 4,
                    'warrior': 5
                }

                health = health_multipliers.get(data['class_name'].lower(), 1) * constitution

                # Store player's current information in the cache

                player_info_cache[unique_id] = {
                    "class": data['class_name'],
                    "race": data['player_race'],
                    "feats": feats,
                    "stats": stats_dict,
                    "health": health,
                    "level": data['player_level'],
                    "remaining_stat_points": data['remaining_stat_points'],
                    "florins": data['florins'],
                    "image_url": image_url,
                    "job": data['job_name'],
                }

            return player_info_cache
async def has_feat(player_id, server_id, feat_name):
    unique_id = f"{player_id}_{server_id}"
    if feat_name in player_info_cache[unique_id]['feats']:
        return 5, feat_name
    else:
        return 0, None
async def check_stat(player_id, server_id, stat_name, min_value, feat_bonus):
    unique_id = f"{player_id}_{server_id}"
    stat_value = player_info_cache[unique_id]['stats'][stat_name]
    roll_result = random.randint(1, 20)
    total_check_value = roll_result + round(stat_value/3) + feat_bonus

    if total_check_value >= min_value:
        return True, roll_result, stat_value, total_check_value
    else:
        return False, roll_result, stat_value, total_check_value
async def challenge_stat_int(ctx, stats):
    view = StatChallengeIntellect1(ctx, stats, ctx.author)
    initial_embed = await view.generate_embed()
    await ctx.send(embed=initial_embed, view=view)

@bot.command(name="test", description="Check your owned cards on the server")
async def _test(ctx):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    unique_id = f"{player_id}_{server_id}"

    if unique_id not in player_info_cache:
        player_info_cache.update(await cache_player_info(player_id, server_id))

    player_stats = player_info_cache[unique_id]['stats']

    await challenge_stat_int(ctx, player_stats)




#Side Questing
class StatChallengeIntellect1(discord.ui.View):
    def __init__(self, ctx, stats, command_user):
        super().__init__()
        self.server_id = ctx.guild.id
        self.player_id = ctx.author.id
        self.ctx = ctx
        self.stats = stats
        self.command_user = command_user
        self.stat_flavors = {
            'intellect': {
                'flavor_text': "Across the room, a hulking statue casts a monstrous silhouette, a hulking, alien "
                               "figure carved from the same dark stone as the surrounding chamber. In its "
                               "outstretched hand, a stone altar sits, dust-covered and adorned with eerie,"
                               " unfamiliar glyphs.",
                'image_url': "https://imagizer.imageshack.com/img923/7384/21Uku8.png",
                'failure_text': "Hours pass, or perhaps only minutes - time seems irrelevant in the heavy air of "
                                "the crypt. Despite your best efforts, the artifact remains as enigmatic as before, "
                                "its secrets sealed within the cold stone. A sense of frustration swells within you. "
                                "The chamber offers no further clues, and you are left with an intriguing mystery and"
                                " a growing sense of unease.",
                'success_text': "As you trace your fingers over the patterns, one glyph in particular draws your "
                                "attention. A sensation, not quite physical but undeniably real, buzzes beneath"
                                " your fingertips. This symbol is not just carved but imbued, enchanted with "
                                "a magic you have rarely felt before."
            }
        }

    async def generate_embed(self):
        stat_value = self.stats['intellect']
        flavor_text = self.stat_flavors['intellect']['flavor_text']
        image_url = self.stat_flavors['intellect']['image_url']

        embed = discord.Embed(title=f"Mystic Altar", description=f"{flavor_text}", color=0x00ff00)
        embed.set_footer(text=f"Intellect Value: {stat_value}")

        embed.set_image(url=image_url)
        return embed

    @discord.ui.button(label='Investigate', style=discord.ButtonStyle.primary)
    async def attempt_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return

        # Check if player has the relevant feat
        feat_bonus, feat_name = await has_feat(self.player_id, self.server_id, 'investigation')

        # Pass the correct arguments to check_stat
        stat_check, roll_result, stat_value, total_check_value = await check_stat(self.player_id, self.server_id,
                                                                                  'intellect', 13, feat_bonus)
        stat_value = round(stat_value / 3)

        if stat_check:
            success_text = self.stat_flavors['intellect']['success_text']
            embed = discord.Embed(title=f"Success!", description=success_text, color=0x00ff00)
            embed.set_footer(
                text=f"You rolled {roll_result} + your skill modifier {stat_value} + {str(feat_bonus) + ' from ' + feat_name if feat_name else ''} for a total of {total_check_value}")
            embed.set_thumbnail(url=self.stat_flavors['intellect']['image_url'])
            await interaction.response.edit_message(embed=embed, view=None)

            # Show new embed with inspect and leave buttons
            view = StatChallengeIntellect2(self.ctx, self.stats, self.command_user)
            inspect_embed = await view.generate_embed()
            await interaction.followup.send(embed=inspect_embed, view=view)
        else:
            failure_text = self.stat_flavors['intellect']['failure_text']
            embed = discord.Embed(title=f"Failure!", description=failure_text, color=0xff0000)
            embed.set_footer(
                text=f"You rolled {roll_result} + your skill modifier {stat_value} + {'feat bonus ' + str(feat_bonus) + ' from ' + feat_name if feat_name else ''} for a total of {total_check_value}")
            embed.set_thumbnail(url=self.stat_flavors['intellect']['image_url'])
            await interaction.response.edit_message(embed=embed, view=self)

            # Remove the Investigate button after a failed attempt
            self.remove_item(self.attempt_button)

    @discord.ui.button(label='Ignore', style=discord.ButtonStyle.danger)
    async def ignore_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Implement the ignore functionality here
        pass
class StatChallengeIntellect2(discord.ui.View):
    def __init__(self, ctx, stats, command_user):
        super().__init__()
        self.server_id = ctx.guild.id
        self.player_id = ctx.author.id
        self.ctx = ctx
        self.stats = stats
        self.command_user = command_user
        self.stat_flavors = {
            'intellect': {
                'flavor_text': "The glyph pulses with an ethereal glow. Do you dare to inspect it further?",
                'image_url': "https://imagizer.imageshack.com/img923/7384/21Uku8.png",
                'failure_text': "Your intellect fails you and the magical energy from the glyph sends a jolt through your body. You reel back, unable to decipher the arcane energy.",
                'success_text': "Your knowledge of the arcane arts allows you to recognize the glyph's magic. It's a symbol of protection, ancient and powerful. This discovery bolsters your party's morale."
            }
        }

    async def generate_embed(self):
        stat_value = self.stats['intellect']
        flavor_text = self.stat_flavors['intellect']['flavor_text']
        image_url = self.stat_flavors['intellect']['image_url']

        embed = discord.Embed(title=f"Glyph of Protection", description=f"{flavor_text}", color=0x00ff00)
        embed.set_footer(text=f"Intellect Value: {stat_value}")

        embed.set_image(url=image_url)
        return embed

    # Modify this method in StatChallengeIntellect2
    @discord.ui.button(label='Inspect', style=discord.ButtonStyle.primary)
    async def inspect_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.command_user.id:
            return

        # Check if player has the relevant feat
        feat_bonus, feat_name = await has_feat(self.player_id, self.server_id, 'arcana')

        # Pass the correct arguments to check_stat
        stat_check, roll_result, stat_value, total_check_value = await check_stat(self.player_id, self.server_id,
                                                                                  'intellect', 255, feat_bonus)
        stat_value = round(stat_value / 3)
        unique_id = f"{self.player_id}_{self.server_id}"
        if stat_check:
            success_text = self.stat_flavors['intellect']['success_text']
            embed = discord.Embed(title=f"Success!", description=success_text, color=0x00ff00)
            embed.set_footer(
                text=f"You rolled {roll_result} + your skill modifier {stat_value} + {'feat bonus ' + str(feat_bonus) + ' from ' + feat_name if feat_name else ''} for a total of {total_check_value}")
            embed.set_thumbnail(url=self.stat_flavors['intellect']['image_url'])
            await interaction.response.send_message(embed=embed)
        else:
            # Deduct health
            failure_text = self.stat_flavors['intellect']['failure_text']
            damage = 3
            player_info_cache[f"{self.player_id}_{self.server_id}"]['health'] -= damage
            remaining_health = player_info_cache[f"{self.player_id}_{self.server_id}"]['health']


            failure_text = self.stat_flavors['intellect']['failure_text']
            embed = discord.Embed(title=f"Failure!", description=f"{failure_text}\n\nThe glyph's magic backlash deals {damage} damage to you.", color=0xff0000)
            embed.set_footer(
                text=f"You rolled {roll_result} + your skill modifier {stat_value} + {'feat bonus ' + str(feat_bonus) + ' from ' + feat_name if feat_name else ''} for a total of {total_check_value}")
            embed.add_field(name="Health Remaining", value=remaining_health, inline=False)
            embed.set_thumbnail(url=self.stat_flavors['intellect']['image_url'])
            await interaction.response.send_message(embed=embed)

    @discord.ui.button(label='Leave', style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Implement the leave functionality here
        pass





bot.run("DISCORD BOT NEEDED.")