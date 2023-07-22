import discord
import random
import asyncio
import Database
import numpy as np
from collections import OrderedDict
from typing import Any

NOTICED_MULTIPLIER = {
    'Common': 0.9,
    'Uncommon': 0.8,
    'Rare': 0.6,
    'Epic': 0.4,
    'Legendary': 0.2,
    'Mythic': 0.1
}
GRUDGE_POINTS_BY_ITEM_RARITY = {
    'Common': 5,
    'Uncommon': 10,
    'Rare': 15,
    'Epic': 20,
    'Legendary': 25,
    'Mythic': 30,
}


#Overall Functions
async def get_noticed(ctx, rogue_agility, guard_intelligence):
    rogue_base_roll = random.randint(1, 20)
    guard_base_roll = random.randint(1, 20)

    rogue_roll = rogue_base_roll + rogue_agility
    guard_roll = guard_base_roll + guard_intelligence

    await ctx.send(
                   f'You roll {rogue_base_roll} + {rogue_agility} = {rogue_roll}  \n'
                   f'Defender rolls {guard_base_roll} + {guard_intelligence} = {guard_roll}')

    if rogue_roll < guard_roll:
        return True
    else:
        return False
async def calculate_escape_chance(ctx, rogue_agility, guard_agility):
    rogue_base_roll = random.randint(1, 20)
    guard_base_roll = random.randint(1, 20)

    rogue_roll = rogue_base_roll + rogue_agility
    guard_roll = guard_base_roll + guard_agility

    await ctx.send(
                   f'You roll {rogue_base_roll} + {rogue_agility} = {rogue_roll}  \n'
                   f'Defender rolls {guard_base_roll} + {guard_agility} = {guard_roll}')


    if rogue_roll > guard_roll:
        return True
    else:
        return False
async def calculate_attack_success(ctx, assassin_attack, guard_attack):
    assassin_base_roll = random.randint(1, 20)
    guard_base_roll = random.randint(1, 20)

    assassin_roll = assassin_base_roll + assassin_attack
    guard_roll = guard_base_roll + guard_attack

    await ctx.send(
                   f'You roll {assassin_base_roll} + {assassin_attack} = {assassin_roll}  \n'
                   f'Defender rolls {guard_base_roll} + {guard_attack} = {guard_roll}')

    if assassin_roll > guard_roll:
        return True
    else:
        return False




#Patron Functions
items_cache = {}

class ItemSelectionView(discord.ui.View):
    def __init__(self, ctx, items, server_id, player_id, conn, pool):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.items = items
        self.current_item_index = 0
        self.server_id = server_id
        self.player_id = player_id
        self.conn = conn
        self.pool = pool

    async def generate_embed(self):
        if not self.items:
            # Handle empty list. Maybe return a special "no items" embed?
            embed = discord.Embed(title="No Items", description="There are currently no items to show.")
            return embed
        item = self.items[self.current_item_index]
        item_id, name, rarity, image_url, buy_price = item.values()
        embed = discord.Embed()
        embed.title = f"Unidentified {name}"
        embed.description = f"Rarity: {rarity}\nBuy price: {buy_price}"
        embed.set_image(url=image_url)
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

    @discord.ui.button(emoji="<:gold:1114517505361326111>", style=discord.ButtonStyle.green)
    async def buy_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        global items_cache

        if interaction.user.id != self.ctx.author.id:
            return

        try:
            selected_item = self.items[self.current_item_index]

            item_price = selected_item['buy_price']

            # Check if the player has enough florins to buy the item
            player_florins = await Database.get_florins(self.server_id, self.player_id)
            if player_florins < item_price:
                await self.ctx.send(
                    f"You don't have enough florins to buy {selected_item['name']}. You have {player_florins} florins.")
                return

            # Deduct the florins
            await Database.deduct_florins(self.server_id, self.player_id, item_price)

            # Claim the item
            claim_success = await Database.claim_item(self.server_id, self.player_id, selected_item['id'])

            if claim_success:
                cache_key = f'{self.server_id}_{self.player_id}'
                if cache_key in items_cache:
                    items_cache[cache_key] = [item for item in items_cache[cache_key] if
                                              item['id'] != selected_item['id']]
                    self.items.pop(self.current_item_index)

                # If we are at the end of the list, loop back to the start
                if self.current_item_index >= len(self.items):
                    self.current_item_index = 0

                await self.ctx.send(
                    f"You have successfully bought {selected_item['name']} for {item_price} florins! You have {player_florins - item_price} florins left.")
            else:
                # Refund the player's florins if claim failed
                await Database.add_florins(self.server_id, self.player_id, item_price)
                await self.ctx.send(
                    f"Something went wrong while claiming your item. Your {item_price} florins have been refunded.")

            # Check if there are items left
            if not self.items:
                # Disable all buttons if no items left
                for component in self.children:
                    if isinstance(component, discord.ui.Button):
                        component.disabled = True
                await self.ctx.send("There are no more items to buy.")
            else:
                # Edit message to show next item
                await interaction.response.edit_message(embed=await self.generate_embed())

        except Exception as e:
            await self.ctx.send(f"No")
async def show_random_items(ctx, server_id, player_id, conn, pool):
    global items_cache

    # Check if the user can perform the action
    can_show, remaining_time = await Database.can_perform_action(player_id, server_id, 'show_random_items', pool, conn)

    # Define rarity-based price here
    rarity_prices = {'common': 350, 'rare': 1450, 'epic': 6700, 'mythic': 32000}

    cache_key = f'{server_id}_{player_id}'

    if not can_show:
        await ctx.send(f"New items in {remaining_time}")
        if cache_key in items_cache:
            items = items_cache[cache_key]
        else:
            await ctx.send(f"New items in {remaining_time}")
            return
    else:
        rarity_weights = {
            'Common': 1
        }

        items = []
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for rarity, weight in rarity_weights.items():
                    print(f'Checking for {rarity} items')
                    try:
                        await cursor.execute("""
                            SELECT id, name, rarity, image_url FROM items
                            WHERE rarity = %s
                        """, (rarity,))
                        items_of_rarity = await cursor.fetchall()
                        if items_of_rarity:
                            # Ensure there are at least 5 items to select from
                            if len(items_of_rarity) >= 5:
                                selected_items = random.sample(items_of_rarity, 5)
                                for item in selected_items:
                                    item_dict = dict(zip(('id', 'name', 'rarity', 'image_url'), item))
                                    item_dict['buy_price'] = rarity_prices.get(item_dict['rarity'].lower(), 0)
                                    items.append(item_dict)
                    except Exception as e:
                        print(f'Error occurred: {e}')

                print(f'items: {items}')

        # Cache the selected items
        items_cache[cache_key] = items

        # Update the action timestamp
        await Database.update_action_timestamp(player_id, server_id, 'show_random_items', False)

    view = ItemSelectionView(ctx, items, server_id, player_id, conn, pool)
    embed = await view.generate_embed()
    await ctx.send(embed=embed, view=view)

#Patron Functions Architect
rarities = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Mythic']
class BuildingSelectionView(discord.ui.View):
    def __init__(self, ctx, buildings, conn, pool, server_id, player_id):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.buildings = buildings
        self.current_building_index = 0
        self.conn = conn
        self.pool = pool
        self.server_id = server_id
        self.player_id = player_id

    async def generate_embed(self):
        building = self.buildings[self.current_building_index]
        building_id, name, image_url, rarity, genre, type, max_claim, claimed_count, destroyed, tier, income, cost, short_title = building
        embed = discord.Embed()
        embed.set_image(url=image_url)
        embed.title = name
        embed.description = short_title
        embed.add_field(name="Cost", value=cost, inline=True)
        embed.add_field(name="Income", value=income, inline=True)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def previous_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_building_index = (self.current_building_index - 1) % len(self.buildings)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_building_index = (self.current_building_index + 1) % len(self.buildings)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Hammer:1113695488626131005>", style=discord.ButtonStyle.green)
    async def select_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        selected_building = self.buildings[self.current_building_index]

        # Check if the user can afford the building
        current_florins = await Database.get_florins(self.server_id, self.player_id)
        if current_florins < selected_building[11]:  # assuming cost is at index 11
            await self.ctx.send("You do not have enough florins to build this.")
            return

        # Deduct the building cost from user's florins
        await Database.deduct_florins(self.server_id, self.player_id, selected_building[11])
        remaining_florins = current_florins - selected_building[11]

        # Add claimed building for the user
        success = await Database.add_claimed_building(self.server_id, self.player_id, selected_building[0])
        if success:
            await self.ctx.send(
                f"You have built '{selected_building[1]}'. It cost you {selected_building[11]} florins. You have {remaining_florins} florins remaining.")
        else:
            await self.ctx.send("Failed to claim the building.")

        self.stop()
class BuildingRebuildView(discord.ui.View):
    def __init__(self, ctx, buildings, conn, pool, server_id, player_id, patron_intelligence):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.buildings = buildings
        self.current_building_index = 0
        self.conn = conn
        self.pool = pool
        self.server_id = server_id
        self.player_id = player_id
        self.patron_intelligence = patron_intelligence

    async def generate_embed(self):
        building = self.buildings[self.current_building_index]
        building_id, name, image_url, rarity, genre, type, max_claim, claimed_count, destroyed, tier, income, cost, short_title = building
        repair_cost = (cost / 2)
        reduction = (0.015 * self.patron_intelligence)
        ramount = round(repair_cost * reduction)
        repair_cost = round(repair_cost - ramount)
        embed = discord.Embed()
        embed.set_image(url=image_url)
        embed.title = name
        embed.description = short_title
        embed.add_field(name="Cost", value=f"{repair_cost} ( {cost / 2} - {ramount} )", inline=True)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def previous_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_building_index = (self.current_building_index - 1) % len(self.buildings)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_building_index = (self.current_building_index + 1) % len(self.buildings)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Hammer:1113695488626131005>", style=discord.ButtonStyle.green)
    async def rebuild_building(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        selected_building = self.buildings[self.current_building_index]
        repair_cost = (selected_building[11] / 2)
        reduction = (0.015 * self.patron_intelligence)
        ramount = (repair_cost * reduction)
        repair_cost = round(repair_cost - ramount)
        user_florins = await Database.get_florins(self.server_id, self.player_id)

        if user_florins < repair_cost:
            await self.ctx.send("You don't have enough florins to repair this building.")
            return

        await Database.deduct_florins(self.server_id, self.player_id, repair_cost)

        # Set building to 'rebuilt'
        await Database.update_building_state(self.server_id, self.player_id, selected_building[0], False)
        await self.ctx.send(f"You have rebuilt '{selected_building[1]}' for {repair_cost} florins.")
        self.stop()
async def _rebuild(ctx, bot, conn, pool):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    # Check if player has a patron role card
    selected_patron_card_id = await Database.get_selected_role_card_id(player_id, server_id, 'patron')
    if selected_patron_card_id is None:
        await ctx.send("You must have a patron to rebuild a building.")
        return

    patron_stats = await Database.get_card_stats(selected_patron_card_id)
    patron_intelligence = patron_stats['intellect']

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT pb.building_id, b.name, b.image_url, b.rarity, b.genre, b.type, b.max_claim, pb.claimed_count, pb.destroyed, b.tier, b.income, b.cost, b.short_title
            FROM buildings b
            INNER JOIN player_buildings pb ON b.id = pb.building_id AND pb.server_id = %s AND pb.player_id = %s
            WHERE pb.destroyed = 1
            ORDER BY b.name ASC
        """, (server_id, player_id))

        destroyed_buildings = await cur.fetchall()

    if not destroyed_buildings:
        await ctx.send("There are no destroyed buildings to select from.")
        return

    view = BuildingRebuildView(ctx, destroyed_buildings, conn, pool, server_id, player_id, patron_intelligence)
    await ctx.send(embed=await view.generate_embed(), view=view)
async def _available_buildings(ctx, bot, conn, pool):
    server_id = ctx.guild.id
    player_id = ctx.author.id

    # Fetch the player's race
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT *
            FROM player_races
            WHERE server_id = %s AND player_id = %s
        """, (server_id, player_id))
        player_race_row = await cur.fetchone()

    if not player_race_row or player_race_row[12] != 1:
        await ctx.send("You haven't progressed far enough in the tutorial. Please run"
                       " \n\n ***$start***\n or\n ***$continue*** \n\n "
                       "to finish.")
        return
    player_race = player_race_row[3].lower()

    # Fetch the player's highest owned castle tier
    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT MAX(b.tier)
            FROM player_buildings pb
            JOIN buildings b ON pb.building_id = b.id
            WHERE pb.player_id = %s AND b.type = 'castle'
        """, (player_id,))
        highest_owned_castle_tier_row = await cur.fetchone()

    highest_owned_castle_tier = highest_owned_castle_tier_row[0] if highest_owned_castle_tier_row else 0
    highest_owned_castle_tier = highest_owned_castle_tier if highest_owned_castle_tier is not None else 0

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT b.id, b.name, b.image_url, b.rarity, b.genre, b.type, b.max_claim, pb.claimed_count, pb.destroyed, b.tier, b.income, b.cost, b.short_title
            FROM buildings b
            LEFT JOIN player_buildings pb ON b.id = pb.building_id AND pb.server_id = %s AND pb.player_id = %s
            WHERE NOT EXISTS (
                SELECT 1 
                FROM player_buildings pb2 
                WHERE pb2.building_id = b.id 
                AND pb2.player_id = %s
            )
            ORDER BY b.name ASC
        """, (server_id, player_id, player_id))

        all_buildings = await cur.fetchall()

    if not all_buildings:
        await ctx.send("There are no available buildings to select from.")
        return

    # Filter available buildings based on game rules
    available_buildings = []
    for building in all_buildings:
        building_id, name, image_url, rarity, genre, type, max_claim, claimed_count, destroyed, tier, income, cost, short_title = building

        # Assign a default value of 0 if tier is None
        tier = tier if tier is not None else 0

        # Only include the building if its tier is less than or equal to the highest owned castle tier or the building type is 'castle'
        if type != 'castle' and tier > highest_owned_castle_tier:
            continue

        # Check if the building genre matches player's race or is 'any'
        if genre != 'any' and genre != player_race:
            continue

        available_buildings.append(building)

    view = BuildingSelectionView(ctx, available_buildings, conn, pool, server_id, player_id)
    await ctx.send(embed=await view.generate_embed(), view=view)



#Rogue Functions Thief
async def _steal_florins(ctx, victim: discord.Member, conn, pool):
    thief_id = ctx.author.id
    victim_id = victim.id
    server_id = ctx.guild.id
    can_steal, remaining_time = await Database.can_perform_action(thief_id, server_id, 'steal', pool, conn)
    guard_genre = None

    if not can_steal:
        await ctx.send(f"You cannot steal right now. Please wait {remaining_time}")
        return

    await ctx.send(
        f"rolling. . . ")
    selected_thief_card_id = await Database.get_selected_role_card_id(thief_id, server_id, 'rogue')

    thief_attack = await Database.get_attack_value(server_id, thief_id, 'rogue')

    if thief_attack is None or thief_attack == 0:
        await ctx.send("You must have a rogue to steal florins.")
        return

    thief_genre = await Database.get_card_genre(selected_thief_card_id)

    if thief_genre == "thief":
        thief_attack *= 1.5

    selected_guard_card_id = await Database.get_selected_role_card_id(victim_id, server_id, 'soldier')

    guard_defense = await Database.get_defense_value(server_id, victim_id, 'soldier')

    if guard_defense is None or guard_defense == 0:
        guard_defense = 0
    else:
        guard_genre = await Database.get_card_genre(selected_guard_card_id)

        if guard_genre == "guard":
            guard_defense *= 1.5

    steal_success_rate = await calculate_attack_success(ctx, thief_attack, guard_defense)
    thief_stats = await Database.get_card_stats(selected_thief_card_id)
    rogue_intelligence = thief_stats['intellect']
    if thief_genre == "thief":
        rogue_intelligence *= 1.5

    if steal_success_rate:
        victim_florins = await Database.get_florins(server_id, victim_id)
        stolen_percentage = rogue_intelligence * 0.01
        stolen_florins = int(victim_florins * stolen_percentage)
        if victim_florins < stolen_florins:
            stolen_florins = victim_florins

        await Database.deduct_florins(server_id, victim_id, stolen_florins)
        await Database.give_florins(server_id, thief_id, stolen_florins)

        await ctx.send(f"Success! you stole {stolen_florins} florins!")
        await Database.update_action_timestamp(thief_id, server_id, 'steal', False)

        guard_stats = await Database.get_card_stats(selected_guard_card_id)
        if guard_stats is not None:
            guard_intelligence = guard_stats['intellect']
            if guard_genre == "guard":
                guard_intelligence *= 1.5
            guard_agility = guard_stats['agility']
            if guard_genre == "guard":
                guard_agility *= 1.5

            # If the thief is noticed, add grudge points
            if await get_noticed(ctx, rogue_intelligence, guard_intelligence):
                grudge_points = stolen_florins // 5
                await Database.add_grudge_points(server_id, thief_id, victim_id, grudge_points)
                escape_chance = await calculate_escape_chance(ctx, rogue_intelligence, guard_agility)

                if escape_chance:
                    await ctx.send(f"You managed to escape!")
                else:
                    altercation_outcome = await calculate_attack_success(ctx,
                                                                         thief_stats['strength'] + thief_stats['agility'],
                                                                         guard_stats['strength'] + guard_stats['agility'] if guard_stats else 0
                                                                         )
                    thief_total_florins = await Database.get_florins(server_id, thief_id)
                    extra_florins = int(thief_total_florins * 0.05)  # calculate 5% of thief's total florins

                    if altercation_outcome:
                        await Database.remove_user_role(server_id, victim_id, 'soldier')
                        await Database.delete_specific_card(server_id, victim_id, selected_guard_card_id)
                        await ctx.send(
                            f"Your rogue won the altercation! {victim.mention}'s soldier was killed. You managed to escape.")
                    else:
                        if extra_florins > thief_total_florins - stolen_florins:
                            extra_florins = thief_total_florins - stolen_florins  # ensure thief is not left with negative florins

                        await Database.deduct_florins(server_id, thief_id,
                                                  stolen_florins + extra_florins)  # deduct stolen and extra florins from thief
                        await Database.give_florins(server_id, victim_id,
                                                stolen_florins + extra_florins)  # return stolen florins and give extra florins to victim

                        await Database.remove_user_role(server_id, thief_id, 'rogue')
                        await Database.delete_specific_card(server_id, thief_id, selected_thief_card_id)

                        await ctx.send(
                            f"You failed to escape! Your rogue was killed. The Target has recovered their stolen florins and received an additional {extra_florins} florins from you.")

    else:
        await ctx.send(f"{victim.mention}'s Guard Spots you, preventing your attempt")
        await Database.update_action_timestamp(thief_id, server_id, 'steal', False)


#Rogue Functions Assassin
class RoleSelectionView(discord.ui.View):
    def __init__(self, ctx, roles, server_id, player_id, conn, pool):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.roles = roles
        self.current_role_index = 0
        self.server_id = server_id
        self.player_id = player_id
        self.conn = conn
        self.pool = pool

    async def generate_embed(self):
        role = self.roles[self.current_role_index]
        role_id, name, image_url, strength, intellect, agility, constitution = role
        embed = discord.Embed()
        embed.set_image(url=image_url)
        embed.title = name
        embed.add_field(name="Strength", value=strength, inline=True)
        embed.add_field(name="Intellect", value=intellect, inline=True)
        embed.add_field(name="Agility", value=agility, inline=True)
        embed.add_field(name="Constitution", value=constitution, inline=True)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_role_index = (self.current_role_index - 1) % len(self.roles)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_role_index = (self.current_role_index + 1) % len(self.roles)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:dagger:1113996766472323113>", style=discord.ButtonStyle.primary)
    async def select_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        selected_role = self.roles[self.current_role_index]

        await interaction.response.send_message(
            f"You have targeted '{selected_role[0]}' for an Assassination attempt.")

        # Pass the selected target directly
        await _assassinate(self.ctx, self.player_id, selected_role[0], self.conn, self.pool)
async def _target_role(ctx, target_user: discord.Member, conn, pool):
    server_id = ctx.guild.id
    target_user_id = target_user.id

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT ur.role, pc.card_name, pc.image_url, pc.strength, pc.intellect, pc.agility, pc.constitution
            FROM user_role_cards ur
            INNER JOIN player_cards pc ON ur.card_id = pc.player_card_id AND ur.server_id = %s AND ur.user_id = %s
            ORDER BY pc.card_name ASC
        """, (server_id, target_user_id))
        target_roles = await cur.fetchall()

    if not target_roles:
        await ctx.send(f"{target_user.mention} doesn't have any roles to select from.")
        return

    view = RoleSelectionView(ctx, target_roles, server_id, target_user.id, conn, pool)
    await ctx.send(embed=await view.generate_embed(), view=view)
async def _assassinate(ctx, target_user: discord.Member, target_role: str, conn, pool):
    server_id = ctx.guild.id
    current_user_id = ctx.author.id
    target_usermen = target_user
    bot = ctx.bot

    print(f'{target_role}')

    selected_target_card_id = await Database.get_selected_role_card_id(target_user, server_id, target_role)
    selected_assassin_card_id = await Database.get_selected_role_card_id(current_user_id, server_id, 'rogue')
    can_assassinate, remaining_time = await Database.can_perform_action(ctx.author.id, server_id, 'assassinate', pool, conn)

    await ctx.send(f"Rolling. . .")

    if not can_assassinate:
        await ctx.send(f"You cannot assassinate right now. Please wait {remaining_time}")
        return

    if selected_assassin_card_id is None:
        await ctx.send(f"You don't have an assassin for this operation.")
        return

    assassin_attack = await Database.get_attack_value(server_id, current_user_id, 'rogue')
    assassin_stats = await Database.get_card_stats(selected_assassin_card_id)
    assassin_genre = await Database.get_card_genre(selected_assassin_card_id)
    target_defense = await Database.get_defense_value(server_id, target_user, target_role)

    assassin_agility = assassin_stats['agility']

    if assassin_genre == "assassin":
        assassin_attack *= 1.5
        assassin_agility *= 1.5

    target_defense = target_defense if target_defense else 0

    assassination_success_rate = await calculate_attack_success(ctx, assassin_attack, target_defense)
    grudge_points = 0

    if assassination_success_rate:
        await Database.update_action_timestamp(current_user_id, server_id, 'assassinate', False)
        await Database.remove_user_role(server_id, target_user, target_role)
        await Database.delete_specific_card(server_id, target_user, selected_target_card_id)

        await ctx.send(f"Success! Your assassin killed {target_role}!")
        grudge_points = 10
    else:
        await ctx.send(f"Targeted {target_role} successfully defended against your assassination attempt!")
        await Database.update_action_timestamp(current_user_id, server_id, 'assassinate', False)
        grudge_points = 3

    selected_guard_card_id = await Database.get_selected_role_card_id(target_user, server_id, 'soldier')
    await Database.add_grudge_points(server_id, current_user_id, target_user, grudge_points)

    if selected_guard_card_id:
        guard_stats = await Database.get_card_stats(selected_guard_card_id)
        guard_genre = await Database.get_card_genre(selected_guard_card_id)

        guard_agility = guard_stats['agility']
        guard_intelligence = guard_stats['intellect']

        if guard_genre == "guard":
            guard_agility *= 1.5
            guard_intelligence *= 1.5

        if await get_noticed(ctx, assassin_agility, guard_intelligence):
            await ctx.send(f"<@{target_usermen}> noticed you, you've received {grudge_points} grudge points.")
            guard_attack = await Database.get_attack_value(server_id, target_user, 'soldier')
            guard_attack = guard_attack * 1.5 if guard_genre == "guard" else guard_attack if guard_attack else 0

            if await calculate_attack_success(ctx, assassin_attack, guard_attack):
                await ctx.send(f"Your assassin managed to escape!")
            else:
                # The guard wins
                await Database.remove_user_role(server_id, current_user_id, 'rogue')
                await Database.delete_specific_card(server_id, current_user_id, selected_assassin_card_id)
                await ctx.send(f"The guard killed your assassin trying to escape!")



#Rogue Functions Thug
class KidnappingRoleSelectionView(discord.ui.View):
    def __init__(self, ctx, roles, server_id, player_id, conn, pool):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.roles = roles
        self.current_role_index = 0
        self.server_id = server_id
        self.player_id = player_id
        self.conn = conn
        self.pool = pool

    async def generate_embed(self):
        role = self.roles[self.current_role_index]
        role_id, name, image_url, strength, intellect, agility, constitution = role
        embed = discord.Embed()
        embed.set_image(url=image_url)
        embed.title = name
        embed.add_field(name="Strength", value=strength, inline=True)
        embed.add_field(name="Intellect", value=intellect, inline=True)
        embed.add_field(name="Agility", value=agility, inline=True)
        embed.add_field(name="Constitution", value=constitution, inline=True)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_role_index = (self.current_role_index - 1) % len(self.roles)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_role_index = (self.current_role_index + 1) % len(self.roles)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:cuffs:1114076341021704213>", style=discord.ButtonStyle.primary)
    async def select_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        selected_role = self.roles[self.current_role_index]

        await interaction.response.send_message(
            f"You have targeted their'{selected_role[0]}' for a Capture attempt.")

        # Directly pass the selected target to the kidnapping function
        await _kidnap(self.ctx, self.player_id, selected_role[0], self.conn, self.pool)
async def _target_role_capture(ctx, target_user: discord.Member, conn, pool):
    server_id = ctx.guild.id
    target_user_id = target_user.id

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT ur.role, pc.card_name, pc.image_url, pc.strength, pc.intellect, pc.agility, pc.constitution
            FROM user_role_cards ur
            INNER JOIN player_cards pc ON ur.card_id = pc.player_card_id AND ur.server_id = %s AND ur.user_id = %s
            ORDER BY pc.card_name ASC
        """, (server_id, target_user_id))
        target_roles = await cur.fetchall()

    if not target_roles:
        await ctx.send(f"{target_user.mention} doesn't have any roles to select from.")
        return

    view = KidnappingRoleSelectionView(ctx, target_roles, server_id, target_user, conn, pool)
    await ctx.send(embed=await view.generate_embed(), view=view)
async def _kidnap(ctx, target_user: discord.Member, target_role: str, conn, pool):
    server_id = ctx.guild.id
    target_user_id = target_user.id
    bot = ctx.bot
    current_user_id = ctx.author.id
    target_usermen = ctx.guild.get_member(target_user_id)

    await ctx.send(f"Rolling. . .")

    can_kidnap, remaining_time = await Database.can_perform_action(ctx.author.id, server_id, 'kidnap', pool, conn)

    selected_target_card_id = await Database.get_selected_role_card_id(target_user, server_id, target_role)
    selected_kidnapper_card_id = await Database.get_selected_role_card_id(current_user_id, server_id, 'rogue')

    if not can_kidnap:
        await ctx.send(f"You cannot capture right now. Please wait {remaining_time}")
        return

    if selected_kidnapper_card_id is None:
        await ctx.send(f"You don't have a Thug for this operation.")
        return

    kidnapper_attack = await Database.get_attack_value(server_id, current_user_id, 'rogue')
    kidnapper_stats = await Database.get_card_stats(selected_kidnapper_card_id)
    kidnapper_genre = await Database.get_card_genre(selected_kidnapper_card_id)
    target_defense = await Database.get_defense_value(server_id, target_user_id, target_role)

    kidnapper_agility = kidnapper_stats['agility']
    kidnapper_strength = kidnapper_stats['strength']

    if kidnapper_genre == "thug":
        kidnapper_attack *= 1.5
        kidnapper_agility *= 1.5
        kidnapper_strength *= 1.5

    target_defense = target_defense if target_defense else 0

    kidnap_success_rate = await calculate_attack_success(ctx, kidnapper_attack, target_defense)
    grudge_points = 0

    if kidnap_success_rate:
        await Database.update_action_timestamp(current_user_id, server_id, 'kidnap', False)

        selected_guard_card_id = await Database.get_selected_role_card_id(target_user_id, server_id, 'soldier')

        if selected_guard_card_id:
            guard_stats = await Database.get_card_stats(selected_guard_card_id)
            guard_genre = await Database.get_card_genre(selected_guard_card_id)

            guard_agility = guard_stats['agility']
            guard_intelligence = guard_stats['intellect']

            if guard_genre == "guard":
                guard_agility *= 1.5
                guard_intelligence *= 1.5

            if await get_noticed(ctx, kidnapper_agility, guard_intelligence):
                await ctx.send(f"<@{target_usermen}> noticed you, you've received {grudge_points} grudge points.")
                guard_attack = await Database.get_attack_value(server_id, target_user_id, 'soldier')
                guard_attack = guard_attack * 1.5 if guard_genre == "guard" else guard_attack if guard_attack else 0

                if await calculate_attack_success(ctx, kidnapper_attack, guard_attack):
                    await Database.remove_user_role(server_id, target_user_id, 'soldier')
                    await Database.delete_specific_card(server_id, target_user_id, selected_guard_card_id)
                    await ctx.send(f"Your Thug killed their guard while escaping!")
                else:
                    await Database.remove_user_role(server_id, current_user_id, 'rogue')
                    await Database.delete_specific_card(server_id, current_user_id, selected_kidnapper_card_id)
                    await ctx.send(f"The guard killed your Thug trying to escape!")

        await Database.remove_user_role(server_id, target_user_id, target_role)
        await Database.transfer_card(server_id, target_user_id, current_user_id, selected_target_card_id, pool)
        await ctx.send(f"Success! Your Thug captured the {target_role}!")
        grudge_points = 10
    else:
        await ctx.send(f"The {target_role} successfully defended against the kidnap attempt!")
        await Database.update_action_timestamp(current_user_id, server_id, 'kidnap', False)
        grudge_points = 3

        selected_guard_card_id = await Database.get_selected_role_card_id(target_user_id, server_id, 'soldier')

        if selected_guard_card_id:
            guard_stats = await Database.get_card_stats(selected_guard_card_id)
            guard_genre = await Database.get_card_genre(selected_guard_card_id)

            guard_agility = guard_stats['agility']
            guard_intelligence = guard_stats['intellect']

            if guard_genre == "guard":
                guard_agility *= 1.5
                guard_intelligence *= 1.5

            if await get_noticed(ctx, kidnapper_agility, guard_intelligence):
                await ctx.send(f"<@{target_usermen}> noticed you, you've received {grudge_points} grudge points.")
                guard_attack = await Database.get_attack_value(server_id, target_user_id, 'soldier')
                guard_attack = guard_attack * 1.5 if guard_genre == "guard" else guard_attack if guard_attack else 0

                if await calculate_attack_success(ctx, kidnapper_attack, guard_attack):
                    await Database.remove_user_role(server_id, target_user_id, 'soldier')
                    await Database.delete_specific_card(server_id, target_user_id, selected_guard_card_id)
                    await ctx.send(f"Your Thug killed their guard while escaping!")
                else:
                    await Database.remove_user_role(server_id, current_user_id, 'rogue')
                    await Database.delete_specific_card(server_id, current_user_id, selected_kidnapper_card_id)
                    await ctx.send(f"The guard killed your Thug trying to escape!")

    await Database.add_grudge_points(server_id, current_user_id, target_user_id, grudge_points)



#Soldier Functions Pillager
class BuildingSelectionViewPil(discord.ui.View):
    def __init__(self, ctx, buildings, server_id, player_id, conn, pool):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.buildings = buildings
        self.current_building_index = 0
        self.server_id = server_id
        self.player_id = player_id
        self.conn = conn
        self.pool = pool

    async def generate_embed(self):
        building = self.buildings[self.current_building_index]
        building_id, name, image_url, rarity, genre, type, max_claim, claimed_count, destroyed, tier, income, cost, short_title = building
        embed = discord.Embed()
        embed.set_image(url=image_url)
        embed.title = name
        embed.add_field(name="Obtainable Loot", value=round(cost * 0.89), inline=True)
        return embed

    @discord.ui.button(emoji="<:Larrow:1106624302268297286>", style=discord.ButtonStyle.secondary)
    async def prev_building_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_building_index = (self.current_building_index - 1) % len(self.buildings)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:Rarrow:1106624275034677360>", style=discord.ButtonStyle.secondary)
    async def next_building_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        self.current_building_index = (self.current_building_index + 1) % len(self.buildings)
        await interaction.response.edit_message(embed=await self.generate_embed())

    @discord.ui.button(emoji="<:torch:1113786351582707864>", style=discord.ButtonStyle.primary)
    async def select_building_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return
        selected_building = self.buildings[self.current_building_index]

        # Ensure the selected building is not destroyed
        if selected_building[8] == 1:  # Assuming destroyed is the 8th index
            await interaction.response.send_message(
                "This building has already been destroyed. Please select a different one.")
            return

        await interaction.response.send_message(
            f"You have targeted building ID '{selected_building[0]}' for a Pillage attempt.")

        # Call the _pillage function directly with selected_building[0]
        await _pillage(self.ctx, self.player_id, selected_building[0], self.conn, self.pool)

        self.stop()
async def _target_building(ctx, target_user: discord.Member, conn, pool):
    server_id = ctx.guild.id
    target_user_id = target_user.id

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT pb.building_id, b.name, b.image_url, b.rarity, b.genre, b.type, b.max_claim, pb.claimed_count, pb.destroyed, b.tier, b.income, b.cost, b.short_title
            FROM buildings b
            INNER JOIN player_buildings pb ON b.id = pb.building_id AND pb.server_id = %s AND pb.player_id = %s AND pb.destroyed = 0
            ORDER BY b.name ASC
        """, (server_id, target_user_id))
        target_buildings = await cur.fetchall()

    if not target_buildings:
        await ctx.send(f"{target_user.mention} doesn't have any buildings to select from.")
        return

    view = BuildingSelectionViewPil(ctx, target_buildings, server_id, target_user, conn, pool)
    await ctx.send(embed=await view.generate_embed(), view=view)
async def _pillage(ctx, target_user: discord.Member, building_id: int, conn, pool):
    server_id = ctx.guild.id
    target_user_id = target_user.id
    current_user_id = ctx.author.id
    target_usermen = ctx.guild.get_member(target_user_id)

    can_pillage, remaining_time = await Database.can_perform_action(ctx.author.id, server_id, 'pillage', pool, conn)

    if not can_pillage:
        await ctx.send(f"You cannot pillage right now. Please wait {remaining_time} .")
        return

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT b.name, b.cost 
            FROM buildings b
            INNER JOIN player_buildings pb ON pb.building_id = b.id
            WHERE pb.server_id = %s AND pb.player_id = %s AND pb.building_id = %s
        """, (server_id, target_user_id, building_id))
        building = await cur.fetchone()

    if not building:
        await ctx.send(f"{target_user.mention} does not have the targeted building.")
        return

    building_name, building_cost = building

    selected_soldier_card_id = await Database.get_selected_role_card_id(current_user_id, server_id, 'soldier')
    selected_guard_card_id = await Database.get_selected_role_card_id(target_user_id, server_id, 'soldier')

    if selected_soldier_card_id is None:
        await ctx.send(f"You don't have a soldier for this operation.")
        return

    pillager_attack = await Database.get_attack_value(server_id, current_user_id, 'soldier')
    guard_defense = await Database.get_defense_value(server_id, target_user_id, 'soldier')

    guard_defense = guard_defense or 0

    soldier_stats = await Database.get_card_stats(selected_soldier_card_id)
    guard_stats = await Database.get_card_stats(selected_guard_card_id) if selected_guard_card_id else None

    pillager_genre = await Database.get_card_genre(selected_soldier_card_id)
    guard_genre = await Database.get_card_genre(selected_guard_card_id) if selected_guard_card_id else None

    if pillager_genre == "pillager":
        pillager_attack *= 1.5

    if guard_genre == "guard":
        guard_defense *= 1.5

    pillage_success_rate = await calculate_attack_success(ctx, pillager_attack, guard_defense)

    if pillage_success_rate:
        await Database.update_action_timestamp(current_user_id, server_id, 'pillage', False)
        reward_percentage = (soldier_stats['agility'] * 0.03)
        reward = round(building_cost * reward_percentage)

        await Database.give_florins(server_id, current_user_id, reward)

        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE player_buildings
                SET destroyed = 1
                WHERE server_id = %s AND player_id = %s AND building_id = %s
            """, (server_id, target_user_id, building_id))

            await conn.commit()
        await ctx.send(f"Success! Your soldier pillaged {building_name} and earned {reward} florins!")

        if await get_noticed(ctx, soldier_stats['agility'], guard_stats['intellect'] if guard_stats else 0):
            grudge_points = reward // 5
            await Database.add_grudge_points(server_id, current_user_id, target_user_id, grudge_points)
            escape_chance = await calculate_escape_chance(ctx, soldier_stats['agility'], guard_stats['agility'] if guard_stats else 0)

            if escape_chance:
                await ctx.send(f"But you managed to escape!")
            else:
                altercation_outcome = await calculate_attack_success(ctx,
                    soldier_stats['strength'] + soldier_stats['agility'],
                    guard_stats['strength'] + guard_stats['agility'] if guard_stats else 0
                )

                pillager_total_florins = await Database.get_florins(server_id, current_user_id)
                extra_florins = int(pillager_total_florins * 0.05)

                if extra_florins > pillager_total_florins - reward:
                    extra_florins = pillager_total_florins - reward

                if altercation_outcome:
                    await ctx.send(
                        f"You managed to escape!")
                else:
                    await Database.deduct_florins(server_id, current_user_id, extra_florins)
                    await Database.give_florins(server_id, target_user_id, extra_florins)
                    await Database.give_florins(server_id, target_user_id, reward)

                    await Database.remove_user_role(server_id, current_user_id, 'soldier')
                    await Database.delete_specific_card(server_id, current_user_id, selected_soldier_card_id)
                    await ctx.send(
                        f"You failed to escape! Your soldier was killed. {target_usermen} has recovered their stolen florins and received an additional {extra_florins} florins from you.")
    else:
        await ctx.send(
            f"{target_usermen}'s soldier defended the building and your pillaging attempt failed!")

        if await get_noticed(ctx, soldier_stats['agility'], guard_stats['intellect'] if guard_stats else 0):
            escape_chance = await calculate_escape_chance(ctx, soldier_stats['agility'],
                                                    guard_stats['agility'] if guard_stats else 0)

            if escape_chance:
                await ctx.send(f"But you managed to escape!")
            else:
                altercation_outcome = await calculate_attack_success(ctx,
                    soldier_stats['strength'] + soldier_stats['agility'],
                    guard_stats['strength'] + guard_stats['agility'] if guard_stats else 0
                )

                pillager_total_florins = await Database.get_florins(server_id, current_user_id)
                extra_florins = int(pillager_total_florins * 0.05)

                if altercation_outcome:
                    await ctx.send(
                        f"You managed to escape!")
                else:  # guard wins
                    await Database.deduct_florins(server_id, current_user_id, extra_florins)
                    await Database.give_florins(server_id, target_user_id, extra_florins)

                    await Database.remove_user_role(server_id, current_user_id, 'soldier')
                    await Database.delete_specific_card(server_id, current_user_id,
                                                        selected_soldier_card_id)
                    await ctx.send(
                        f"You failed to escape! Your soldier was killed. {target_usermen} received {extra_florins} from your soldier\'s corpse.")