import aiomysql
import datetime
import asyncio
from dateutil.tz import tzutc
import pytz
import discord
import random
from cachetools import LRUCache, cached


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
    'roll': one_hour,
    'collect': testing,
    'steal': testing,
    'kidnap': testing,
    'roll_quest': testing,
    'roll_shop': testing,
    'assassinate': testing,
    'pillage': testing,
    'sue': testing,
    'roll_quests': testing,
    'show_random_items': testing,
    'work': testing
}

pool = None
conn = None

DB_NAME = "MYSQL needed"
DB_HOST = "MYSQL needed"
DB_USER = "MYSQL needed"
DB_PASS = "MYSQL needed"

async def init_db_fin():
    global pool
    global conn
    pool = await aiomysql.create_pool(host=DB_HOST, port=25060,
                                      user=DB_USER, password=DB_PASS,
                                      db=DB_NAME, autocommit=True)
async def init_db():
    global pool
    global conn
    pool = await aiomysql.create_pool(host=DB_HOST, port=25060,
                                      user=DB_USER, password=DB_PASS,
                                      db=DB_NAME, autocommit=True)
    conn = await pool.acquire()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INT PRIMARY KEY AUTO_INCREMENT,
                rarity VARCHAR(255) NOT NULL,
                race VARCHAR(255) NOT NULL,
                genre VARCHAR(255) NOT NULL,
                type VARCHAR(255) NOT NULL,
                min_strength INT NOT NULL,
                max_strength INT NOT NULL,
                min_intellect INT NOT NULL,
                max_intellect INT NOT NULL,
                min_agility INT NOT NULL,
                max_agility INT NOT NULL,
                min_constitution INT NOT NULL,
                max_constitution INT NOT NULL,
                max_claim INT NOT NULL DEFAULT 500000
            );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_cards (
                    player_card_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    card_id INT NOT NULL,
                    card_name VARCHAR(255) NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    strength INT,
                    intellect INT,
                    agility INT,
                    constitution INT,
                    claimed_count INT NOT NULL DEFAULT 0,
                    FOREIGN KEY (card_id) REFERENCES cards (id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_florins (
                    user_id BIGINT NOT NULL,
                    server_id BIGINT NOT NULL,
                    florins INT NOT NULL,
                    last_collect TIMESTAMP,
                    PRIMARY KEY (user_id, server_id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_cooldowns (
                        user_id BIGINT NOT NULL,
                        server_id BIGINT NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_count INT NOT NULL DEFAULT 0,
                        last_performed TIMESTAMP,
                        PRIMARY KEY (user_id, server_id, action)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_role_cards (
                    user_id BIGINT NOT NULL,
                    server_id BIGINT NOT NULL,
                    role VARCHAR(255) NOT NULL,
                    card_id INT NOT NULL,
                    FOREIGN KEY (card_id) REFERENCES player_cards (player_card_id),
                    PRIMARY KEY (user_id, server_id, role),
                    INDEX role_index (role)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS buildings (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        name VARCHAR(255) NOT NULL,
                        image_url VARCHAR(255) NOT NULL,
                        rarity VARCHAR(255) NOT NULL,
                        genre VARCHAR(255) NOT NULL,
                        type VARCHAR(255) NOT NULL,
                        short_title VARCHAR(255),
                        max_claim INT NOT NULL DEFAULT 500000,
                        tier INT NOT NULL,
                        income INT NOT NULL,
                        cost INT NOT NULL
                    );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_buildings (
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    building_id INT NOT NULL,
                    claimed_count INT NOT NULL DEFAULT 0,
                    destroyed TINYINT(1) NOT NULL DEFAULT 0,
                    FOREIGN KEY (building_id) REFERENCES buildings (id),
                    PRIMARY KEY (server_id, player_id, building_id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS grudges (
                    server_id BIGINT NOT NULL,
                    attacker_id BIGINT NOT NULL,
                    victim_id BIGINT NOT NULL,
                    grudge_points INT NOT NULL DEFAULT 0,
                    PRIMARY KEY (server_id, attacker_id, victim_id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_races (
                    player_race_id INT AUTO_INCREMENT UNIQUE,
                    server_id BIGINT  NOT NULL,
                    player_id BIGINT  NOT NULL,
                    player_race VARCHAR(255) NOT NULL,
                    gnome_allied TINYINT(1) DEFAULT 0,
                    human_allied TINYINT(1) DEFAULT 0,
                    orc_allied TINYINT(1) DEFAULT 0,
                    goblin_allied TINYINT(1) DEFAULT 0,
                    dwarf_allied TINYINT(1) DEFAULT 0,
                    elf_allied TINYINT(1) DEFAULT 0,
                    racial_1 TINYINT(1) DEFAULT 1,
                    racial_2 TINYINT(1) DEFAULT 0,
                    racial_3 TINYINT(1) DEFAULT 0,
                    PRIMARY KEY (server_id, player_id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS campaign_quests (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(255) NOT NULL,
                    race VARCHAR(255) NOT NULL,
                    intel_level INT NOT NULL,
                    class VARCHAR(255) NOT NULL,
                    total_stages INT NOT NULL,
                    description TEXT,
                    image_url VARCHAR(255),
                    reward VARCHAR(255) NOT NULL
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_campaign_progress (
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    quest_id INT NOT NULL,
                    player_stage INT NOT NULL DEFAULT 0,
                    completed BOOLEAN NOT NULL DEFAULT 0,
                    choice VARCHAR(255),
                    choice2 VARCHAR(255),
                    choice3 VARCHAR(255),
                    FOREIGN KEY (quest_id) REFERENCES campaign_quests (id),
                    PRIMARY KEY (server_id, player_id, quest_id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_classes (
                    player_class_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    class_name VARCHAR(255) NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    strength INT DEFAULT 0,
                    intellect INT DEFAULT 0,
                    agility INT DEFAULT 0,
                    constitution INT DEFAULT 0,
                    player_level INT DEFAULT 1,
                    remaining_stat_points INT DEFAULT 0
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_feats (
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    Stealth INT DEFAULT 0,
                    Acrobatics INT DEFAULT 0,
                    Deception INT DEFAULT 0,
                    Insight INT DEFAULT 0,
                    Intimidation INT DEFAULT 0,
                    Investigation INT DEFAULT 0,
                    Medicine INT DEFAULT 0,
                    Religion INT DEFAULT 0,
                    Persuasion INT DEFAULT 0,
                    Performance INT DEFAULT 0,
                    Perception INT DEFAULT 0,
                    Arcana INT DEFAULT 0,
                    Remaining_Points INT DEFAULT 3,
                    PRIMARY KEY (server_id, player_id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(255) NOT NULL,
                    rarity VARCHAR(255) NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    type VARCHAR(255) NOT NULL,
                    race VARCHAR(255) NOT NULL,
                    level INT NOT NULL,
                    min_strength INT NOT NULL,
                    max_strength INT NOT NULL,
                    min_intellect INT NOT NULL,
                    max_intellect INT NOT NULL,
                    min_agility INT NOT NULL,
                    max_agility INT NOT NULL,
                    min_constitution INT NOT NULL,
                    max_constitution INT NOT NULL
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_items (
                    player_item_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    item_id INT NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    level INT NOT NULL,
                    strength INT,
                    intellect INT,
                    agility INT,
                    constitution INT,
                    damaged TINYINT(1) NOT NULL DEFAULT 0,
                    identified TINYINT(1) NOT NULL DEFAULT 0,
                    enchantment_1 VARCHAR(255),
                    enchantment_2 VARCHAR(255),
                    enchantment_3 VARCHAR(255),
                    curse_1 VARCHAR(255),
                    curse_2 VARCHAR(255),
                    FOREIGN KEY (item_id) REFERENCES items (id)
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_gear (
                    player_job_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    armor_item_id INT DEFAULT NULL,
                    single_item_id INT DEFAULT NULL,
                    both_item_id INT DEFAULT NULL,
                    off_item_id INT DEFAULT NULL,
                    ring_item_id INT DEFAULT NULL,
                    amulet_item_id INT DEFAULT NULL,
                    tool_item_id INT DEFAULT NULL,
                    helmet_item_id INT DEFAULT NULL,
                    special_item_id INT DEFAULT NULL,
                    cape_item_id INT DEFAULT NULL,
                    enchanted_item_id INT DEFAULT NULL
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_jobs (
                    player_job_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    job_name VARCHAR(255) NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    Proficiency INT DEFAULT 0,
                    Stamina INT DEFAULT 0,
                    Focus INT DEFAULT 0,
                    job_level INT DEFAULT 1,
                    remaining_stat_points INT DEFAULT 0
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_resources (
                    player_res_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    Oak_logs INT DEFAULT 0,
                    Maple_logs INT DEFAULT 0,
                    Yew_logs INT DEFAULT 0,
                    BlackAsh_logs INT DEFAULT 0,
                    Celestial_logs INT DEFAULT 0,
                    Mushrooms INT DEFAULT 0,
                    Elf_Thistle INT DEFAULT 0,
                    Ember_Root INT DEFAULT 0,
                    Shadow_Moss INT DEFAULT 0,
                    Mithril_Weed INT DEFAULT 0,
                    Iron_ore INT DEFAULT 0,
                    Silver_ore INT DEFAULT 0,
                    Gold_ore INT DEFAULT 0,
                    Titanium_ore INT DEFAULT 0,
                    Mithril_ore INT DEFAULT 0,
                    Topaz INT DEFAULT 0,
                    Sapphire INT DEFAULT 0,
                    Ruby INT DEFAULT 0,
                    Diamond INT DEFAULT 0,
                    Primordial_Onyx INT DEFAULT 0,
                    Cotton INT DEFAULT 0,
                    Flax INT DEFAULT 0,
                    FireBloom INT DEFAULT 0,
                    Runeleaf INT DEFAULT 0,
                    Spellweave_Fiber INT DEFAULT 0,
                    Hide INT DEFAULT 0,
                    Silk INT DEFAULT 0,
                    Shadow_Pelt INT DEFAULT 0,
                    Wyrmwing_Scales INT DEFAULT 0,
                    Dragon_Scales INT DEFAULT 0,
                    Tattered_Parchment INT DEFAULT 0,
                    Faded_Parchment INT DEFAULT 0,
                    Moonlit_Parchment INT DEFAULT 0,
                    Abyssal_Parchment INT DEFAULT 0,
                    Celestial_Parchment INT DEFAULT 0,
                    Faded_shard INT DEFAULT 0,
                    Emblem INT DEFAULT 0,
                    Crimson_Orb INT DEFAULT 0,
                    Mythril_Amulet INT DEFAULT 0,
                    Divine_Relic INT DEFAULT 0,
                    Proficiency INT DEFAULT 0,
                    Stamina INT DEFAULT 0,
                    Focus INT DEFAULT 0,
                    job_level INT DEFAULT 1,
                    remaining_stat_points INT DEFAULT 0
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_crafted_items (
                    player_res_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    Sprigs_Sip INT DEFAULT 0,
                    Mead_of_Mending INT DEFAULT 0,
                    Elixir_of_Restoration INT DEFAULT 0,
                    Nectar_of_Renewal INT DEFAULT 0,
                    Ambrosia_of_Life INT DEFAULT 0,
                    Panacea_of_Divinity INT DEFAULT 0,
                    Wayfarer_Bread INT DEFAULT 0,
                    Dwarf_Delight INT DEFAULT 0,
                    Heroes_Feast INT DEFAULT 0,
                    Gourmets_Grace INT DEFAULT 0,
                    Elysian_Meal INT DEFAULT 0,
                    Warders_Whisper INT DEFAULT 0,
                    wolfs_howl INT DEFAULT 0,
                    Firebrand INT DEFAULT 0,
                    Frostbite INT DEFAULT 0,
                    Dragons_Breath INT DEFAULT 0,
                    Celestial_Brilliance INT DEFAULT 0,
                    Pads INT DEFAULT 0,
                    Ironclad INT DEFAULT 0,
                    Steel_Bastion INT DEFAULT 0,          
                    Mithril_Ward INT DEFAULT 0,
                    Celestial_Mantle INT DEFAULT 0,
                    Lockpicks INT DEFAULT 0,
                    Slippery_Spheres INT DEFAULT 0,
                    Nightwalker_paint INT DEFAULT 0,
                    Shadowmantle INT DEFAULT 0,
                    Skeleton_Key INT DEFAULT 0
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS server_crafted_items (
                    player_res_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    Sprigs_Sip INT DEFAULT 0,
                    Mead_of_Mending INT DEFAULT 0,
                    Elixir_of_Restoration INT DEFAULT 0,
                    Nectar_of_Renewal INT DEFAULT 0,
                    Ambrosia_of_Life INT DEFAULT 0,
                    Panacea_of_Divinity INT DEFAULT 0,
                    Wayfarer_Bread INT DEFAULT 0,
                    Dwarf_Delight INT DEFAULT 0,
                    Heroes_Feast INT DEFAULT 0,
                    Gourmets_Grace INT DEFAULT 0,
                    Elysian_Meal INT DEFAULT 0,
                    Warders_Whisper INT DEFAULT 0,
                    wolfs_howl INT DEFAULT 0,
                    Firebrand INT DEFAULT 0,
                    Frostbite INT DEFAULT 0,
                    Dragons_Breath INT DEFAULT 0,
                    Celestial_Brilliance INT DEFAULT 0,
                    Pads INT DEFAULT 0,
                    Ironclad INT DEFAULT 0,
                    Steel_Bastion INT DEFAULT 0,          
                    Mithril_Ward INT DEFAULT 0,
                    Celestial_Mantle INT DEFAULT 0,
                    Lockpicks INT DEFAULT 0,
                    Slippery_Spheres INT DEFAULT 0,
                    Nightwalker_paint INT DEFAULT 0,
                    Shadowmantle INT DEFAULT 0,
                    Skeleton_Key INT DEFAULT 0
                );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS server_resources (
                    server_res_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    Oak_logs INT DEFAULT 0,
                    Maple_logs INT DEFAULT 0,
                    Yew_logs INT DEFAULT 0,
                    BlackAsh_logs INT DEFAULT 0,
                    Celestial_logs INT DEFAULT 0,
                    Mushrooms INT DEFAULT 0,
                    Elf_Thistle INT DEFAULT 0,
                    Ember_Root INT DEFAULT 0,
                    Shadow_Moss INT DEFAULT 0,
                    Mithril_Weed INT DEFAULT 0,
                    Iron_ore INT DEFAULT 0,
                    Silver_ore INT DEFAULT 0,
                    Gold_ore INT DEFAULT 0,
                    Titanium_ore INT DEFAULT 0,
                    Mithril_ore INT DEFAULT 0,
                    Topaz INT DEFAULT 0,
                    Sapphire INT DEFAULT 0,
                    Ruby INT DEFAULT 0,
                    Diamond INT DEFAULT 0,
                    Primordial_Onyx INT DEFAULT 0,
                    Cotton INT DEFAULT 0,
                    Flax INT DEFAULT 0,
                    FireBloom INT DEFAULT 0,
                    Runeleaf INT DEFAULT 0,
                    Spellweave_Fiber INT DEFAULT 0,
                    Hide INT DEFAULT 0,
                    Silk INT DEFAULT 0,
                    Shadow_Pelt INT DEFAULT 0,
                    Wyrmwing_Scales INT DEFAULT 0,
                    Dragon_Scales INT DEFAULT 0,
                    Tattered_Parchment INT DEFAULT 0,
                    Faded_Parchment INT DEFAULT 0,
                    Moonlit_Parchment INT DEFAULT 0,
                    Abyssal_Parchment INT DEFAULT 0,
                    Celestial_Parchment INT DEFAULT 0,
                    Faded_shard INT DEFAULT 0,
                    Emblem INT DEFAULT 0,
                    Crimson_Orb INT DEFAULT 0,
                    Mythril_Amulet INT DEFAULT 0,
                    Divine_Relic INT DEFAULT 0
                );
            """)
            await cur.execute("""
            CREATE TABLE IF NOT EXISTS spells (
                id INT PRIMARY KEY AUTO_INCREMENT,
                spell_name VARCHAR(255) NOT NULL,
                race VARCHAR(255) NOT NULL,
                class VARCHAR(255) NOT NULL,
                type VARCHAR(255) NOT NULL,
                special_one VARCHAR(255) NOT NULL,
                special_two VARCHAR(255) NOT NULL,
                level INT NOT NULL,
                min_power INT NOT NULL,
                max_power INT NOT NULL,
                unstable INT NOT NULL
            );
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS player_professions (
                    player_job_id INT AUTO_INCREMENT PRIMARY KEY,
                    server_id BIGINT NOT NULL,
                    player_id BIGINT NOT NULL,
                    job_name VARCHAR(255) NOT NULL,
                    image_url VARCHAR(255) NOT NULL,
                    job_level INT DEFAULT 1,
                    EXP INT default 0,
                    remaining_stat_points INT DEFAULT 0
                );
            """)
            await conn.commit()


#Time Management
user_cooldowns_cache = {}
async def update_action_timestamp(user_id, server_id, action, has_aya_chosen_role):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT MAX(b.tier) FROM player_buildings pb
                INNER JOIN buildings b ON pb.building_id = b.id
                WHERE pb.player_id = %s AND pb.server_id = %s AND b.type = 'tavern'
            """, (user_id, server_id))
            max_tavern_tier = await cursor.fetchone()

    if max_tavern_tier[0] is None:
        max_rolls = MAX_ROLLS
    else:
        max_rolls = MAX_ROLLS + max_tavern_tier[0]

    last_performed, action_count = user_cooldowns_cache.get((user_id, server_id, action), (None, 0))
    if last_performed:
        now = datetime.datetime.now(tzutc())
        cooldown_duration = COOLDOWNS.get(action)
        if cooldown_duration is not None and now - last_performed < cooldown_duration and action_count < max_rolls:
            # update action_count in cache
            user_cooldowns_cache[(user_id, server_id, action)] = (last_performed, action_count + 1)
            return
    # update both last_performed and action_count in cache
    now = datetime.datetime.now(tzutc())
    user_cooldowns_cache[(user_id, server_id, action)] = (now, 1)

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO user_cooldowns (user_id, server_id, action, action_count, last_performed)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                action_count = VALUES(action_count),
                last_performed = VALUES(last_performed);
            """, (user_id, server_id, action, action_count, now))
            await conn.commit()
async def can_perform_action(user_id, server_id, action, pool, conn):
    if action == 'roll':
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT MAX(b.tier) FROM player_buildings pb
                    INNER JOIN buildings b ON pb.building_id = b.id
                    WHERE pb.player_id = %s AND pb.server_id = %s AND b.type = 'tavern'
                """, (user_id, server_id))
                max_tavern_tier = await cursor.fetchone()
                if max_tavern_tier[0] is None:
                    max_action_count = MAX_ROLLS
                else:
                    max_action_count = MAX_ROLLS + max_tavern_tier[0]
    elif action not in COOLDOWNS:
        raise ValueError(f"Unknown action: {action}")
    else:
        max_action_count = 1

    cooldown_duration = COOLDOWNS[action]
    last_performed, action_count = user_cooldowns_cache.get((user_id, server_id, action), (None, 0))
    if last_performed:
        cooldown_end = last_performed + cooldown_duration
        now = datetime.datetime.now(pytz.utc)
        if now < cooldown_end and action_count >= max_action_count:
            remaining_time = cooldown_end - now
            remaining_hours = round(remaining_time.total_seconds() / 3600)
            return False, f"{remaining_hours} hours"
    return True, None














#Claiming item cards
ENCHANTMENTS = ['Wrath', 'Resurgence', 'Havoc', 'Secrets', 'Tranquility', 'Slaughter',
                'Empowerment', 'Embrace', 'Extinction', 'Chaos']
CURSES = ['Decayed', 'Hexed', 'Plagued', 'Dammed', 'Regretful', 'Betraying', 'Honorbound']
async def get_item(item_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
            item = await cur.fetchone()
        if item is not None:
            columns = [desc[0] for desc in cur.description]
            item = dict(zip(columns, item))
        return item
async def claim_item(server_id, player_id, item_id):
    print(f"Attempting to claim item {item_id} for player {player_id}")

    item = await get_item(item_id)
    if item is None:
        print(f"Item {item_id} does not exist")
        return False
    print(f'item : : :{item}')

    level = item['level']
    strength = random.randint(item['min_strength'], item['max_strength'])
    intellect = random.randint(item['min_intellect'], item['max_intellect'])
    agility = random.randint(item['min_agility'], item['max_agility'])
    constitution = random.randint(item['min_constitution'], item['max_constitution'])

    weights_enchantment_1 = [70] * len(ENCHANTMENTS) + [30]
    enchantment_1 = random.choices(ENCHANTMENTS + [None], weights=weights_enchantment_1, k=1)[0]

    weights_enchantment_2 = [30] * len(ENCHANTMENTS) + [70]
    enchantment_2 = random.choices(ENCHANTMENTS + [None], weights=weights_enchantment_2, k=1)[
        0] if enchantment_1 else None

    weights_enchantment_3 = [8] * len(ENCHANTMENTS) + [92]
    enchantment_3 = random.choices(ENCHANTMENTS + [None], weights=weights_enchantment_3, k=1)[
        0] if enchantment_2 else None

    weights_curse_1 = [40] * len(CURSES) + [60]
    curse_1 = random.choices(CURSES + [None], weights=weights_curse_1, k=1)[0]

    weights_curse_2 = [5] * len(CURSES) + [95]
    curse_2 = random.choices(CURSES + [None], weights=weights_curse_2, k=1)[0] if curse_1 else None

    damaged = random.choice([0, 1])

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO player_items (server_id, player_id, item_id, name, image_url, level, strength, intellect, agility, constitution, damaged, enchantment_1, enchantment_2, enchantment_3, curse_1, curse_2)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (server_id, player_id, item_id, item['name'], item['image_url'], level, strength, intellect, agility,
                  constitution, damaged, enchantment_1, enchantment_2, enchantment_3, curse_1, curse_2))

    return cursor.rowcount > 0
class IdentifyItemView(discord.ui.View):
    def __init__(self, ctx, items, server_id, player_id, conn, pool):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.items = items
        self.current_item_index = 0
        self.server_id = server_id
        self.player_id = player_id
        self.conn = conn
        self.pool = pool
        self.costs = {
            1: 100,
            2: 200,
            3: 300,
            # Continue this for as many levels as you have
        }

    async def generate_embed(self):
        item = self.items[self.current_item_index]
        embed = discord.Embed()

        # The item is unidentified
        embed.title = f"Unidentified {item['name']}"
        embed.description = "This item is unidentified. Its stats are unknown."

        embed.set_image(url=item['image_url'])
        embed.set_footer(
            text=f"Level: {item['level']} | Cost to identify: {self.costs.get(item['level'], 1000)} florins")
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def previous_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_item_index = (self.current_item_index - 1) % len(self.items)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_item_index = (self.current_item_index + 1) % len(self.items)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="Identify", style=discord.ButtonStyle.primary)
    async def identify_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return

        item = self.items[self.current_item_index]
        cost = self.costs.get(item['level'], 1000)  # default to 1000 if level is not in costs

        if await get_florins(self.server_id, self.player_id) < cost:
            await interaction.response.send_message("You don't have enough florins to identify this item.",
                                                    ephemeral=True)
            return

        # Deduct florins from user's account
        await deduct_florins(self.server_id, self.player_id, cost)

        remaining_florins = await get_florins(self.server_id, self.player_id)

        # Identify the item
        async with self.conn.cursor() as cursor:
            await cursor.execute("""
                UPDATE player_items
                SET identified = 1
                WHERE player_item_id = %s
            """, (item['player_item_id'],))
            await self.conn.commit()

        # Prepare the item name
        item_name = []
        if item['curse_1']:
            item_name.append(item['curse_1'])
        item_name.append(item['name'])
        if item['enchantment_1']:
            item_name.append(f"of {item['enchantment_1']}")

        # Prepare the list of enchantments and curses
        enchantments = []
        curses = []

        if item['enchantment_1']:
            enchantments.append(item['enchantment_1'])
        if item['enchantment_2']:
            enchantments.append(item['enchantment_2'])
        if item['enchantment_3']:
            enchantments.append(item['enchantment_3'])

        if item['curse_1']:
            curses.append(item['curse_1'])
        if item['curse_2']:
            curses.append(item['curse_2'])

        # Send a message about the identified item
        await self.ctx.send(
            f"You identified the {' '.join(item_name)}"
        )

        # Remove the item from the list and show the next one
        self.items.pop(self.current_item_index)
        self.current_item_index = self.current_item_index % len(self.items) if self.items else None

        if self.items:
            await interaction.response.edit_message(embed=await self.generate_embed())
        else:
            await interaction.response.send_message("You have identified all your items.", ephemeral=True)
            self.stop()
async def identify_item(ctx, server_id, player_id, bot, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT *
                FROM player_items
                WHERE server_id = %s AND player_id = %s AND identified = 0
                ORDER BY name ASC
            """, (server_id, player_id,))

            items = await cursor.fetchall()

            if not items:
                await ctx.send("You don't have any unidentified items.")
                return

            # Get the column names from the cursor description
            column_names = [column[0] for column in cursor.description]

            # Convert tuples to dictionaries
            items = [dict(zip(column_names, item)) for item in items]

            view = IdentifyItemView(ctx, items, server_id, player_id, conn, pool)
            await ctx.send(embed=await view.generate_embed(), view=view)
async def check_equipped_items(ctx, server_id, player_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT * FROM plaer_gear 
                WHERE server_id = %s AND player_id = %s
            """, (server_id, player_id,))
            gear_data = await cursor.fetchone()

            slot_to_item_id = {
                "Armor": gear_data['armor_item_id'],
                "Single Handed Weapon": gear_data['single_item_id'],
                "Two Handed Weapon": gear_data['both_item_id'],
                "Off Hand": gear_data['off_item_id'],
                "Ring": gear_data['ring_item_id'],
                "Amulet": gear_data['amulet_item_id'],
                "Tool": gear_data['tool_item_id'],
                "Helmet": gear_data['helmet_item_id'],
                "Special": gear_data['special_item_id'],
                "Cape": gear_data['cape_item_id'],
                "Enchanted": gear_data['enchanted_item_id'],
            }

            slot_to_item_name = {}
            for slot, item_id in slot_to_item_id.items():
                if item_id is not None:
                    await cursor.execute("""
                        SELECT * FROM player_items
                        WHERE player_item_id = %s
                    """, (item_id,))
                    item_data = await cursor.fetchone()

                    # Assemble the item's name
                    item_name = []
                    if item_data['curse_1']:
                        item_name.append(item_data['curse_1'])
                    item_name.append(item_data['name'])
                    if item_data['enchantment_1']:
                        item_name.append(f"of {item_data['enchantment_1']}")

                    slot_to_item_name[slot] = ' '.join(item_name)

            # Generate the embed
            embed = discord.Embed(title=f"{ctx.author.name}'s Equipment", color=0x3498db)
            for slot, item_name in slot_to_item_name.items():
                embed.add_field(name=slot, value=item_name, inline=False)

        await ctx.send(embed=embed)










#Claiming unit cards
async def get_card(card_id):
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT * FROM cards WHERE id = %s", (card_id,))
            return await cursor.fetchone()
async def claim_card(server_id, player_id, card_id):
    print(f"Attempting to claim card {card_id} for player {player_id} on server {server_id}")

    card = await get_card(card_id)
    if card is None:
        print(f"Card {card_id} does not exist")
        return False

    strength = random.randint(card['min_strength'], card['max_strength'])
    intellect = random.randint(card['min_intellect'], card['max_intellect'])
    agility = random.randint(card['min_agility'], card['max_agility'])
    constitution = random.randint(card['min_constitution'], card['max_constitution'])

    print(f" race {card['race']} genre {card['genre']} , type {card['type']}")

    names_race = names.get(card['race'], {})
    names_genre = names_race.get(card['genre'], {})
    name_list = names_genre.get(card['type'], [])

    images_race = images.get(card['race'], {})
    images_genre = images_race.get(card['genre'], {})
    images_type = images_genre.get(card['type'], {})
    image_list = images_type.get(card['rarity'].lower(), [])

    if not name_list or not image_list:
        return False  # Or handle the situation differently

    name = random.choice(name_list)
    image = random.choice(image_list)

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO player_cards (server_id, player_id, card_id, card_name, image_url, strength, intellect, agility, constitution, claimed_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE
                claimed_count = claimed_count + 1,
                card_name = %s,
                image_url = %s,
                strength = %s,
                intellect = %s,
                agility = %s,
                constitution = %s
            """, (server_id, player_id, card_id, name, image, strength, intellect, agility, constitution, name, image, strength, intellect, agility, constitution))

    return cursor.rowcount > 0
async def get_most_recent_player_card(user_id, server_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT * FROM player_cards
                WHERE player_id = %s AND server_id = %s
                ORDER BY player_card_id DESC
                LIMIT 1
            """, (user_id, server_id))
            result = await cursor.fetchone()
            return result










#Claiming building cards
async def add_claimed_building(server_id: int, player_id: int, building_id: int) -> bool:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO player_buildings (server_id, player_id, building_id, claimed_count)
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE claimed_count = claimed_count + 1
            """, (server_id, player_id, building_id))

            await conn.commit()

        return True
async def update_building_state(server_id, player_id, building_id, destroyed):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    UPDATE player_buildings 
                    SET destroyed = %s 
                    WHERE server_id = %s AND player_id = %s AND building_id = %s
                """, (destroyed, server_id, player_id, building_id))
                await conn.commit()
    except Exception as e:
        print(f"Error occurred: {e}")











#Checking Claims
class CardSelectionView(discord.ui.View):
    def __init__(self, ctx, cards, allow_selection, role_type, pool, server_id, player_id):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.cards = cards
        self.current_card_index = 0
        self.allow_selection = allow_selection
        self.role_type = role_type
        self.pool = pool
        self.server_id = server_id
        self.player_id = player_id

        self.select_card_button.disabled = not self.allow_selection

    async def generate_embed(self):
        card = self.cards[self.current_card_index]
        card_id, name, image_url, rarity, race, genre, card_type, strength, intellect, agility, constitution, claimed_count = card
        embed = discord.Embed(title=name, description=f'{rarity} {race} {genre} {card_type}')
        embed.set_image(url=image_url)
        footer_text = f'Str: {strength} | Int: {intellect} | Agi: {agility} | Con: {constitution} | '
        footer_text +=f'Card {self.current_card_index + 1} of {len(self.cards)}'
        embed.set_footer(text=footer_text)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_card_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_card_index = (self.current_card_index - 1) % len(self.cards)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_card_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_card_index = (self.current_card_index + 1) % len(self.cards)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Enlist:1106633767684153405>", style=discord.ButtonStyle.primary)
    async def select_card_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id or not self.allow_selection:
            return
        selected_card = self.cards[self.current_card_index]

        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT player_card_id
                    FROM player_cards
                    WHERE server_id = %s AND player_id = %s AND card_id = %s
                """, (self.server_id, self.player_id, selected_card[0]))
                player_card_id_result = await cursor.fetchone()

                if player_card_id_result is None:
                    return

                player_card_id = player_card_id_result[0]
                await conn.begin()

                try:
                    await cursor.execute("""
                        DELETE FROM user_role_cards
                        WHERE user_id = %s AND server_id = %s AND role = %s
                    """, (self.player_id, self.server_id, self.role_type))
                    await cursor.execute("""
                        INSERT INTO user_role_cards (user_id, server_id, role, card_id)
                        VALUES (%s, %s, %s, %s)
                    """, (self.player_id, self.server_id, self.role_type, player_card_id))
                    await conn.commit()
                    await interaction.response.send_message(f"You have selected {selected_card[1]} as your {self.role_type}.")
                except Exception as e:
                    await conn.rollback()
                    print(f"An error occurred: {str(e)}")

                self.stop()
class ItemSelectionView(discord.ui.View):
    def __init__(self, ctx, items, server_id, player_id, conn, pool):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.player_id = ctx.author.id
        self.server_id = ctx.guild.id
        self.items = items
        self.current_item_index = 0
        self.conn = conn
        self.pool = pool

    def calculate_item_value(self, item):
        if item['identified'] != 1:
            return 50

        rarity_factor = 1
        stat_sum = item['strength'] + item['intellect'] + item['agility'] + item['constitution']
        stat_sum *= 8
        enchantment_factor = len(
            [enchantment for enchantment in [item['enchantment_1'], item['enchantment_2'], item['enchantment_3']] if
             enchantment])
        enchantment_factor *= 100
        curse_factor = len([curse for curse in [item['curse_1'], item['curse_2']] if curse])
        curse_factor *= 150
        return max(25, int(rarity_factor * stat_sum + enchantment_factor - curse_factor))

    async def remove_item_from_inventory(self, item):
        print("Inside remove_item_from_inventory")
        async with self.conn.cursor() as cursor:
            await cursor.execute("""
                DELETE FROM player_items
                WHERE server_id = %s AND player_id = %s AND player_item_id = %s
            """, (self.server_id, self.player_id, item['player_item_id'],))
            print(f"Rows affected: {cursor.rowcount}")  # Add this line
            await self.conn.commit()
        print("Executed SQL command and committed changes")

    async def generate_embed(self):
        item = self.items[self.current_item_index]
        embed = discord.Embed()

        if item['identified'] == 1:
            item_name = []
            if item['curse_1']:
                item_name.append(item['curse_1'])
            item_name.append(item['name'])
            if item['enchantment_1']:
                item_name.append(f"of {item['enchantment_1']}")

            embed.title = ' '.join(item_name)

            item_description = []

            enchantments = []
            curses = []

            if item['enchantment_1']:
                enchantments.append(item['enchantment_1'])
            if item['enchantment_2']:
                enchantments.append(item['enchantment_2'])
            if item['enchantment_3']:
                enchantments.append(item['enchantment_3'])
            if enchantments:
                item_description.append("Enchants: " + ', '.join(enchantments))

            if item['curse_1']:
                curses.append(item['curse_1'])
            if item['curse_2']:
                curses.append(item['curse_2'])
            if curses:
                item_description.append("Curses: " + ', '.join(curses))

            embed.description = '\n'.join(item_description)

            footer = []
            footer.append("Level: " + str(item['level']))
            if item['strength'] > 0:
                footer.append("Strength: " + str(item['strength']))
            if item['intellect'] > 0:
                footer.append("Intellect: " + str(item['intellect']))
            if item['agility'] > 0:
                footer.append("Agility: " + str(item['agility']))
            if item['constitution'] > 0:
                footer.append("Constitution: " + str(item['constitution']))
            embed.set_footer(text=' | '.join(footer))

            footer.append(f"\nSell Value: {self.calculate_item_value(item)} Florins")
            embed.set_footer(text='   '.join(footer))


        else:
            embed.title = f"Unidentified {item['name']}"
            embed.description = "This item is unidentified. Its stats are unknown."
            embed.set_footer(text=f"Level: {item['level']} | Sell Value: 50 Florins")
        embed.set_image(url=item['image_url'])
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def previous_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_item_index = (self.current_item_index - 1) % len(self.items)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_item_index = (self.current_item_index + 1) % len(self.items)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(label="Sell", style=discord.ButtonStyle.danger)
    async def sell_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        item = self.items[self.current_item_index]
        item_value = self.calculate_item_value(item)
        new_florins = await give_florins(self.server_id, self.player_id, item_value)
        print(f'item: {item}')
        await self.remove_item_from_inventory(item)

        # Remove the item from the items list
        self.items.pop(self.current_item_index)

        # If current_item_index is now out of range, reset it to the last item
        if self.current_item_index >= len(self.items):
            self.current_item_index = len(self.items) - 1

        # Update the message to reflect the item list change
        if self.items:
            await interaction.response.edit_message(embed=await self.generate_embed())
            await interaction.followup.send(
                f"Sold {item['name']} for {item_value} florins. You now have {new_florins} florins.", ephemeral=True)
        else:
            await interaction.response.edit_message(content="All items have been sold.", embed=None)
            await interaction.followup.send(
                f"Sold {item['name']} for {item_value} florins. You now have {new_florins} florins.", ephemeral=True)

    @discord.ui.button(label="Equip", style=discord.ButtonStyle.primary)
    async def equip_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        item = self.items[self.current_item_index]
        item_id = item['player_item_id']
        item_type = await get_item_type(self.conn, item['item_id'])  # Retrieve item type asynchronously

        async with self.conn.cursor() as cursor:
            if item_type == 'both':
                await cursor.execute("""
                    INSERT INTO player_gear (server_id, player_id, both_item_id)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE both_item_id = VALUES(both_item_id), off_item_id = NULL, single_item_id = NULL
                """, (self.server_id, self.player_id, item_id))

            elif item_type in ['off', 'single']:
                await cursor.execute("""
                    INSERT INTO player_gear (server_id, player_id, {0}_item_id)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE {0}_item_id = VALUES({0}_item_id), both_item_id = NULL
                """.format(item_type), (self.server_id, self.player_id, item_id))

            else:
                await cursor.execute("""
                    INSERT INTO player_gear (server_id, player_id, {0}_item_id)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE {0}_item_id = VALUES({0}_item_id)
                """.format(item_type), (self.server_id, self.player_id, item_id))

            await self.conn.commit()

        await interaction.response.defer()
        await interaction.followup.send(f"You equipped {item['name']}.", ephemeral=True)
async def get_item_type(conn, item_id):
    async with conn.cursor() as cursor:
        await cursor.execute("""
            SELECT type 
            FROM items
            WHERE id = %s
        """, (item_id,))
        result = await cursor.fetchone()
        return result[0] if result else None
async def check_owned_cards(ctx, server_id, player_id, bot, pool, card_type=None, allow_selection=False, role_type=None):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            card_type_condition = f"AND c.genre = '{card_type}'" if card_type else ""
            await cursor.execute(f"""
                SELECT c.id, pc.card_name, pc.image_url, c.rarity, c.race, c.genre, c.type, pc.strength, pc.intellect, pc.agility, pc.constitution, pc.claimed_count
                FROM player_cards pc
                INNER JOIN cards c ON pc.card_id = c.id
                WHERE pc.server_id = %s AND pc.player_id = %s AND pc.claimed_count > 0 {card_type_condition}
                ORDER BY pc.card_name ASC
            """, (server_id, player_id))

            cards = await cursor.fetchall()

            if not cards:
                await ctx.send(f"You don't own any {card_type} cards on this server.")
                return []

            view = CardSelectionView(ctx, cards, allow_selection, role_type, pool, server_id, player_id)
            await ctx.send(embed=await view.generate_embed(), view=view)
async def check_owned_items(ctx, server_id, player_id, bot, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT *
                FROM player_items
                WHERE server_id = %s AND player_id = %s
                ORDER BY name ASC
            """, (server_id, player_id,))

            items = await cursor.fetchall()

            if not items:
                await ctx.send("You don't own any items on this server.")
                return []

            # Get the column names from the cursor description
            column_names = [column[0] for column in cursor.description]

            # Convert tuples to dictionaries
            items = [dict(zip(column_names, item)) for item in items]

            view = ItemSelectionView(ctx, items, server_id, player_id, conn, pool)
            await ctx.send(embed=await view.generate_embed(), view=view)










#Removing Claims
async def delete_specific_card(server_id, user_id, card_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Begin transaction
            await conn.begin()

            await cursor.execute("""
                DELETE FROM player_cards
                WHERE server_id = %s AND player_id = %s AND player_card_id = %s
            """, (server_id, user_id, card_id))
            result = await cursor.fetchall()
            print(result)
            # Commit the transaction
            await conn.commit()
async def transfer_card(server_id, from_user_id, to_user_id, card_id, pool):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Begin transaction
            await conn.begin()

            await cursor.execute("""
                UPDATE player_cards
                SET player_id = %s
                WHERE server_id = %s AND player_id = %s AND player_card_id = %s
            """, (to_user_id, server_id, from_user_id, card_id))

            await conn.commit()
async def remove_user_role(server_id, user_id, role):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await conn.begin()
            await cursor.execute("""
                DELETE FROM user_role_cards
                WHERE server_id = %s AND user_id = %s AND role = %s
            """, (server_id, user_id, role))
            await conn.commit()










#florins
async def get_florins(server_id: int, user_id: int) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT florins FROM user_florins WHERE server_id = %s AND user_id = %s
            """, (server_id, user_id,))
            result = await cursor.fetchone()

    if result is None:
        return 0
    else:
        return result[0]
async def give_florins(server_id, user_id, amount):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO user_florins (server_id, user_id, florins)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE florins = florins + VALUES(florins)
            """, (server_id, user_id, amount))
            await conn.commit()
            # Fetch the updated florins
            await cursor.execute("""
                SELECT florins FROM user_florins WHERE server_id = %s AND user_id = %s
            """, (server_id, user_id,))
            result = await cursor.fetchone()
            total_florins = result[0] if result else amount

    return total_florins
async def deduct_florins(server_id: int, user_id: int, amount: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                UPDATE user_florins
                SET florins = GREATEST(0, florins - %s)
                WHERE server_id = %s AND user_id = %s
            """, (amount, server_id, user_id,))
            await conn.commit()
async def collect_income(ctx, bot):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT SUM(b.income)
                FROM player_buildings pb
                JOIN buildings b ON pb.building_id = b.id
                WHERE pb.server_id = %s AND pb.player_id = %s
            """, (server_id, player_id))
            total_income_row = await cursor.fetchone()

    if not total_income_row or total_income_row[0] is None:
        await ctx.send("You have no buildings generating income.")
        return

    total_income = total_income_row[0]
    total_income = total_income
    total_florins = await give_florins(server_id, player_id, total_income)
    await ctx.send(f"You have collected {total_income} florins. You now have {total_florins} florins.")











#Get stats
cache = LRUCache(maxsize=10000)
RARITY_VALUES = {
    "Common": 3,
    "Uncommon": 5,
    "Rare": 7,
    "Epic": 9,
    "Legendary": 11,
    "Mythic": 13
}
@cached(cache)
async def get_selected_role_level(user_id, server_id, role):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT c.rarity
                FROM user_role_cards urc
                INNER JOIN cards c ON urc.card_id = c.id
                WHERE urc.user_id = %s AND urc.server_id = %s AND urc.role = %s
            """, (user_id, server_id, role))
            result = await cursor.fetchone()

            if result is None:
                return None

            return result[0]
@cached(cache)
async def get_card_rarity(card_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT rarity
                FROM cards
                WHERE id = %s
            """, (card_id,))
            result = await cursor.fetchone()

            if result is None:
                return None

            return result[0]
async def get_card_stats(player_card_id):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT card_id, strength, intellect, agility, constitution
                FROM player_cards
                WHERE player_card_id = %s
            """, (player_card_id,))
            result = await cursor.fetchone()

            if result is None:
                return None

            card_stats = {
                "card_id": result[0],
                "strength": result[1],
                "intellect": result[2],
                "agility": result[3],
                "constitution": result[4]
            }

            return card_stats
async def get_building_rarity(server_id, user_id, building_type):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT b.rarity 
                FROM player_buildings pb 
                JOIN buildings b ON pb.building_id = b.id 
                WHERE pb.server_id = %s AND pb.player_id = %s AND b.type = %s
                ORDER BY b.rarity DESC
                LIMIT 1
            """, (server_id, user_id, building_type))

            result = await cursor.fetchone()
    return result[0] if result else None
async def get_attack_or_defense_value(server_id, user_id, role, is_attack=True):
    role_card_id = await get_selected_role_card_id(user_id, server_id, role)
    if role_card_id is None:
        return 0
    card_stats = await get_card_stats(role_card_id)
    if card_stats is None:
        return 0
    card_id = card_stats['card_id']
    strength = card_stats['strength']
    intellect = card_stats['intellect']
    agility = card_stats['agility']
    constitution = card_stats['constitution']

    # Fetch genre from cards table
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT genre
                FROM cards
                WHERE id = %s
            """, (int(card_id)))
            result = await cursor.fetchone()
    if result is None:
        return 0
    genre, = result
    value = strength if is_attack else constitution
    if genre == "mystic" and is_attack:
        value = intellect
    elif genre == "rogue" and is_attack:
        value = agility

    building_type = 'blacksmith' if is_attack else 'wall'
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT tier 
                FROM player_buildings 
                INNER JOIN buildings ON player_buildings.building_id = buildings.id 
                WHERE server_id = %s AND player_id = %s AND type = %s
            """, (int(server_id), int(user_id), building_type))
            result = await cursor.fetchone()
    if result is not None:
        tier, = result
        value += tier * 3  # add 3 times the tier to the attack or defense value

    return value
async def get_attack_value(server_id, user_id, role):
    return await get_attack_or_defense_value(server_id, user_id, role, True)
async def get_defense_value(server_id, user_id, role):
    return await get_attack_or_defense_value(server_id, user_id, role, False)









#Get information
async def execute_query(query, params):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            return await cursor.fetchone()
async def get_selected_role_card_id(user_id, server_id, role):
    query = """
        SELECT card_id
        FROM user_role_cards
        WHERE user_id = %s AND server_id = %s AND role = %s
    """
    result = await execute_query(query, (user_id, server_id, role))
    return result[0] if result else None
async def get_card_genre(card_id):
    query = """
        SELECT genre
        FROM cards
        WHERE id = %s
    """
    result = await execute_query(query, (card_id,))
    return result[0] if result else None








#Law system
async def add_grudge_points(server_id, attacker_id, victim_id, points):
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                INSERT INTO grudges (server_id, attacker_id, victim_id, grudge_points)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE grudge_points = grudge_points + %s
            """, (server_id, attacker_id, victim_id, points, points))
            await conn.commit()









