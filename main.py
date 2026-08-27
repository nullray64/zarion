import os
import time
import collections
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands

import config
import database

# Инициализация интентов
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Переменные для отслеживания активности утки
message_timestamps = collections.deque()
duck_active = False

# Ограничение на фарм коинов за чат (раз в 30 секунд)
msg_cooldowns = {}

# --- Вспомогательные функции ---
def make_embed(title: str, description: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=config.EMBED_COLOR)
    embed.set_author(name=config.SERVER_NAME, icon_url=config.SERVER_AVATAR_URL or None)
    return embed

def is_admin(interaction: discord.Interaction) -> bool:
    roles = [r.id for r in interaction.user.roles]
    return config.ROLE_ADMIN_1_ID in roles or config.ROLE_ADMIN_2_ID in roles

def is_support(interaction: discord.Interaction) -> bool:
    roles = [r.id for r in interaction.user.roles]
    return is_admin(interaction) or config.ROLE_SUPPORT_ID in roles

def is_creative(interaction: discord.Interaction) -> bool:
    roles = [r.id for r in interaction.user.roles]
    return is_admin(interaction) or config.ROLE_CREATIVE_ID in roles

async def log_event(guild: discord.Guild, embed: discord.Embed):
    channel = guild.get_channel(config.CHANNEL_LOGS_ID)
    if channel:
        await channel.send(embed=embed)

# --- ИНТЕРФЕЙС ЗАЯВОК (UI) ---

class StaffApplyModal(discord.ui.Modal, title="Заявка в Staff"):
    role_choice = discord.ui.TextInput(label="Выбранная роль", required=True)
    experience = discord.ui.TextInput(label="Почему именно вы?", style=discord.TextStyle.paragraph, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        req_channel = interaction.guild.get_channel(config.CHANNEL_REQ_ID)
        if not req_channel:
            await interaction.response.send_message("Ошибка: Канал заявок не найден.", ephemeral=True)
            return

        embed = make_embed("Новая заявка в Staff", f"**Кандидат:** {interaction.user.mention}\n**Желаемая роль:** {self.role_choice.value}\n**О себе:** {self.experience.value}")
        embed.set_footer(text=f"ID: {interaction.user.id}")

        await req_channel.send(embed=embed, view=StaffApproveView(applicant_id=interaction.user.id, role_name=self.role_choice.value))
        await interaction.response.send_message("Ваша заявка успешно отправлена!", ephemeral=True)

class StaffApplySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Support", description="Модерация и порядок на сервере"),
            discord.SelectOption(label="Creative", description="Проведение ивентов и активностей")
        ]
        super().__init__(placeholder="Выберите желаемую роль...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_role = self.values[0]
        modal = StaffApplyModal()
        modal.role_choice.default = selected_role
        await interaction.response.send_modal(modal)

class StaffApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(StaffApplySelect())

class StaffApproveView(discord.ui.View):
    def __init__(self, applicant_id: int, role_name: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.role_name = role_name

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("Недостаточно прав.", ephemeral=True)
        
        member = interaction.guild.get_member(self.applicant_id)
        if member:
            role_id = config.ROLE_SUPPORT_ID if "Support" in self.role_name else config.ROLE_CREATIVE_ID
            role = interaction.guild.get_role(role_id)
            if role:
                await member.add_roles(role)
                await log_event(interaction.guild, make_embed("Staff Назначение", f"Администратор {interaction.user.mention} одобрил заявку {member.mention} на роль {role.name}."))
                await interaction.response.send_message(f"Заявка одобрена, роль {role.name} выдана.", ephemeral=True)
                self.stop()
                return
        await interaction.response.send_message("Пользователь или роль не найдены.", ephemeral=True)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            return await interaction.response.send_message("Недостаточно прав.", ephemeral=True)
        
        await log_event(interaction.guild, make_embed("Staff Отклонение", f"Администратор {interaction.user.mention} отклонил заявку пользователя <@{self.applicant_id}>."))
        await interaction.response.send_message("Заявка отклонена.", ephemeral=True)
        self.stop()

# --- КНОПКА ЛОВЛИ УТКИ ---
class DuckCatchView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Поймать!", style=discord.ButtonStyle.primary, emoji="🦆")
    async def catch(self, interaction: discord.Interaction, button: discord.ui.Button):
        global duck_active
        if not duck_active:
            return await interaction.response.send_message("Утка уже улетела!", ephemeral=True)
        
        duck_active = False
        await database.add_coins(interaction.user.id, config.DUCK_REWARD_COINS)
        await interaction.response.send_message(f"🎉 {interaction.user.mention} поймал утку и получил {config.DUCK_REWARD_COINS} коинов!")
        self.stop()

# --- СОБЫТИЯ И ЛОГИ ---

@bot.event
async def on_ready():
    await database.init_db()
    voice_rewards.start()
    print(f"Бот {bot.user} успешно запущен!")
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} слэш-команд.")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    embed = make_embed("Вход участника", f"{member.mention} (`{member.id}`) присоединился к серверу.")
    await log_event(member.guild, embed)

@bot.event
async def on_member_remove(member: discord.Member):
    embed = make_embed("Выход участника", f"{member.mention} (`{member.id}`) покинул сервер.")
    await log_event(member.guild, embed)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.nick != after.nick:
        embed = make_embed("Изменение ника", f"**Пользователь:** {after.mention}\n**Старый ник:** {before.nick}\n**Новый ник:** {after.nick}")
        await log_event(after.guild, embed)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or before.content == after.content:
        return
    embed = make_embed("Редактирование сообщения", f"**Автор:** {before.author.mention}\n**Канал:** {before.channel.mention}\n**Было:** {before.content}\n**Стало:** {after.content}")
    await log_event(before.guild, embed)

@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return
    embed = make_embed("Удаление сообщения", f"**Автор:** {message.author.mention}\n**Канал:** {message.channel.mention}\n**Содержимое:** {message.content}")
    await log_event(message.guild, embed)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Экономика за сообщения
    now = time.time()
    user_id = message.author.id
    if user_id not in msg_cooldowns or now - msg_cooldowns[user_id] > 30:
        msg_cooldowns[user_id] = now
        await database.add_coins(user_id, config.COINS_PER_MESSAGE)

    # Триггер Утки
    global duck_active
    message_timestamps.append(now)
    # Удаляем timestamps старше 1 часа
    while message_timestamps and now - message_timestamps[0] > 3600:
        message_timestamps.popleft()

    if len(message_timestamps) >= config.DUCK_MSG_THRESHOLD and not duck_active:
        duck_active = True
        message_timestamps.clear()
        embed = make_embed("Появилась утка!", "(•ө•) КРЯ! Быстрее нажимай кнопку, чтобы поймать!")
        await message.channel.send(embed=embed, view=DuckCatchView())

    await bot.process_commands(message)

# Начисление коинов за Голосовые каналы (каждую минуту)
@tasks.loop(minutes=1)
async def voice_rewards():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and not member.voice.self_deaf and not member.voice.deaf:
                    await database.add_coins(member.id, config.COINS_PER_VOICE_MINUTE)

# --- СЛЭШ КОМАНДЫ (COMMANDS) ---

# --- Staff Инициализация панели ---
@bot.tree.command(name="setup_apply", description="[Admin] Разместить панель подачи заявок в Staff")
async def setup_apply(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    embed = make_embed("Набор в Команду Staff", "Выберите роль из списка ниже и назовите причину, почему именно вы должны стать частью нашей команды.")
    await interaction.channel.send(embed=embed, view=StaffApplyView())
    await interaction.response.send_message("Панель успешно установлена!", ephemeral=True)

# --- Наказания (Support & Admin) ---
@bot.tree.command(name="warn", description="[Support] Выдать предупреждение")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
    if not is_support(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    warns = await database.add_warn(member.id)
    embed = make_embed("Выдано предупреждение", f"**Участник:** {member.mention}\n**Модератор:** {interaction.user.mention}\n**Причина:** {reason}\n**Всего варнов:** {warns}/3")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

    if warns >= 3:
        await member.ban(reason="Достигнут лимит в 3 предупреждения")
        await database.reset_warns(member.id)
        ban_embed = make_embed("Автоматический Бан", f"Участник {member.mention} забанен за получение 3-х варнов.")
        await log_event(interaction.guild, ban_embed)

@bot.tree.command(name="mute", description="[Support] Таймаут участнику (в минутах)")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Не указана"):
    if not is_support(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    duration = timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    embed = make_embed("Выдан Мут (Таймаут)", f"**Участник:** {member.mention}\n**Длительность:** {minutes} мин.\n**Модератор:** {interaction.user.mention}\n**Причина:** {reason}")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

@bot.tree.command(name="ban", description="[Support] Забанить участника")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Не указана"):
    if not is_support(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    await member.ban(reason=reason)
    embed = make_embed("Выдан Бан", f"**Участник:** {member.mention}\n**Модератор:** {interaction.user.mention}\n**Причина:** {reason}")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

# --- Ивенты (Creative & Admin) ---
@bot.tree.command(name="create_event_channel", description="[Creative] Создать канал в категории Event")
async def create_event_channel(interaction: discord.Interaction, name: str, is_voice: bool = False):
    if not is_creative(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    category = interaction.guild.get_channel(config.CATEGORY_EVENT_ID)
    if is_voice:
        ch = await interaction.guild.create_voice_channel(name=name, category=category)
    else:
        ch = await interaction.guild.create_text_channel(name=name, category=category)
    
    embed = make_embed("Создан Ивент-Канал", f"**Канал:** {ch.mention}\n**Создатель:** {interaction.user.mention}")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

@bot.tree.command(name="reward_event", description="[Creative] Наградить участника ивента (1000 коинов)")
async def reward_event(interaction: discord.Interaction, member: discord.Member):
    if not is_creative(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    await database.add_coins(member.id, config.EVENT_REWARD_COINS)
    embed = make_embed("Награда за Ивент", f"{member.mention} получил `{config.EVENT_REWARD_COINS}` коинов от {interaction.user.mention}!")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

# --- Назначение Staff (Admin Only) ---
@bot.tree.command(name="staff_add", description="[Admin] Назначить Staff")
async def staff_add(interaction: discord.Interaction, member: discord.Member, role_type: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    role_id = config.ROLE_SUPPORT_ID if role_type.lower() == "support" else config.ROLE_CREATIVE_ID
    role = interaction.guild.get_role(role_id)
    await member.add_roles(role)
    embed = make_embed("Назначение Staff", f"{interaction.user.mention} выдал роль {role.name} пользователю {member.mention}.")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

@bot.tree.command(name="staff_remove", description="[Admin] Снять Staff")
async def staff_remove(interaction: discord.Interaction, member: discord.Member, role_type: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("Отказано в доступе.", ephemeral=True)
    
    role_id = config.ROLE_SUPPORT_ID if role_type.lower() == "support" else config.ROLE_CREATIVE_ID
    role = interaction.guild.get_role(role_id)
    await member.remove_roles(role)
    embed = make_embed("Снятие Staff", f"{interaction.user.mention} снял роль {role.name} с пользователя {member.mention}.")
    await interaction.response.send_message(embed=embed)
    await log_event(interaction.guild, embed)

# --- Пользовательская Экономика ---
@bot.tree.command(name="balance", description="Проверить свой баланс коинов")
async def balance(interaction: discord.Interaction):
    user_data = await database.get_user(interaction.user.id)
    embed = make_embed("Ваш Баланс", f"У вас на счету: `{user_data['coins']}` коинов.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pay", description="Передать коины (Комиссия 2%)")
async def pay(interaction: discord.Interaction, recipient: discord.Member, amount: int):
    if amount <= 0 or recipient.bot or recipient.id == interaction.user.id:
        return await interaction.response.send_message("Некорректная сумма или получатель.", ephemeral=True)

    success = await database.remove_coins(interaction.user.id, amount)
    if not success:
        return await interaction.response.send_message("У вас недостаточно коинов.", ephemeral=True)

    tax = int(amount * config.TRANSFER_TAX_RATE)
    final_amount = amount - tax
    await database.add_coins(recipient.id, final_amount)

    embed = make_embed("Перевод Коинов", f"Вы успешно перевели `{final_amount}` коинов пользователю {recipient.mention}.\n(Комиссия 2%: `{tax}` коинов)")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy_role", description="Купить кастомную роль (2000 коинов)")
async def buy_role(interaction: discord.Interaction, name: str, color_hex: str):
    success = await database.remove_coins(interaction.user.id, config.COST_CUSTOM_ROLE)
    if not success:
        return await interaction.response.send_message("У вас недостаточно коинов (нужно 2000).", ephemeral=True)

    try:
        color_int = int(color_hex.lstrip('#'), 16)
        role = await interaction.guild.create_role(name=name, color=discord.Color(color_int))
        await interaction.user.add_roles(role)
        embed = make_embed("Покупка Роли", f"Вы создали и получили роль {role.mention}!")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await database.add_coins(interaction.user.id, config.COST_CUSTOM_ROLE)
        await interaction.response.send_message(f"Ошибка при создании роли. Проверьте HEX-код (например #ff0000). Коины возвращены.", ephemeral=True)

@bot.tree.command(name="buy_voice", description="Создать личный ГС (10000 коинов)")
async def buy_voice(interaction: discord.Interaction, channel_name: str):
    success = await database.remove_coins(interaction.user.id, config.COST_PRIVATE_VOICE)
    if not success:
        return await interaction.response.send_message("У вас недостаточно коинов (нужно 10000).", ephemeral=True)

    category = interaction.channel.category
    voice_ch = await interaction.guild.create_voice_channel(name=channel_name, category=category)
    embed = make_embed("Покупка Личного ГС", f"Ваш личный голосовой канал {voice_ch.mention} создан!")
    await interaction.response.send_message(embed=embed)

# --- Мини-игра в Города ---
active_cities_game = {}

@bot.tree.command(name="cities_start", description="Начать игру в города")
async def cities_start(interaction: discord.Interaction):
    ch_id = interaction.channel_id
    if ch_id in active_cities_game:
        return await interaction.response.send_message("Игра в города уже идет в этом канале!", ephemeral=True)
    
    active_cities_game[ch_id] = {"last_letter": None, "used": set()}
    embed = make_embed("Игра в Города", "Игра началась! Назовите любой город с помощью `/cities_play <город>`.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cities_play", description="Назвать город")
async def cities_play(interaction: discord.Interaction, city: str):
    ch_id = interaction.channel_id
    if ch_id not in active_cities_game:
        return await interaction.response.send_message("В этом канале еще не начали игру. Начните с `/cities_start`.", ephemeral=True)

    game = active_cities_game[ch_id]
    city_clean = city.strip().capitalize()
    
    if city_clean.lower() in game["used"]:
        return await interaction.response.send_message(f"Город `{city_clean}` уже был назван!", ephemeral=True)

    first_char = city_clean[0].lower()
    if game["last_letter"] and first_char != game["last_letter"]:
        return await interaction.response.send_message(f"Город должен начинаться на букву **{game['last_letter'].upper()}**!", ephemeral=True)

    # Определение последней валидной буквы (пропуск ь, ъ, ы)
    last_char = city_clean[-1].lower()
    if last_char in ['ь', 'ъ', 'ы']:
        last_char = city_clean[-2].lower()

    game["used"].add(city_clean.lower())
    game["last_letter"] = last_char

    embed = make_embed("Ход в Городах", f"{interaction.user.mention} назвал **{city_clean}**!\nСледующему игроку на букву **{last_char.upper()}**.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cities_stop", description="Завершить игру в города")
async def cities_stop(interaction: discord.Interaction):
    ch_id = interaction.channel_id
    if ch_id in active_cities_game:
        del active_cities_game[ch_id]
        await interaction.response.send_message("Игра в города завершена.")
    else:
        await interaction.response.send_message("Активной игры нет.", ephemeral=True)

bot.run(config.TOKEN)