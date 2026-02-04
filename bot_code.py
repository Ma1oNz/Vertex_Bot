# bot_code.py
import os
import sys
import platform
import asyncio
import json
import random
import string
import hashlib
import tempfile

import discord
from discord.ui import Button, View, Modal, TextInput, Select
from discord.ext import commands
from discord import app_commands

from cryptography.fernet import Fernet
from dotenv import load_dotenv


# ================== ENV ДЕШИФРОВКА ==================

def decrypt_env():
    enc_file = ".env.enc"
    key_file = "env.key"

    if not os.path.exists(enc_file):
        raise FileNotFoundError(f"{enc_file} не найден. Сначала зашифруй .env через encrypt_env.py")

    if not os.path.exists(key_file):
        raise FileNotFoundError(f"{key_file} не найден. Без него нельзя расшифровать .env.enc")

    with open(key_file, "rb") as f:
        key = f.read()

    fernet = Fernet(key)

    with open(enc_file, "rb") as f:
        enc_data = f.read()

    data = fernet.decrypt(enc_data)

    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


env_path = decrypt_env()
load_dotenv(dotenv_path=env_path)
os.remove(env_path)

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID'))
MOD_ROLE_ID = int(os.getenv('MOD_ROLE_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID'))
AUTOROLE_ID = int(os.getenv('AUTOROLE_ID'))

COMMAND_COOLDOWN = {}
ADMIN_ROLES = [1247810993480798290, 1459246098169335840]

BOT_VERSION = "v3.5"
OWNER_ID = 977927782405386290

user_message_log = {}
muted_users = set()
join_log = {}

MUTE_ROLE_ID = None  # если есть роль мьюта, укажи её ID здесь

# Роли, которым разрешена команда !опл
OPL_PAYMENT_ROLES = [
    1468329497962217654,
    1468329498670792927,
    1468329501321724012,
    1468329503469080831,
    1468329507709522136,
    1468329508900966686
]


def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            "welcome_message": "Добро пожаловать на сервер!",
            "autorole_id": None,
            "blocked_users": [],
            "antispam": {
                "enabled": True,
                "messages_per_interval": 5,
                "interval_seconds": 7,
                "mute_seconds": 300
            },
            "antiraid": {
                "enabled": True,
                "joins_per_interval": 5,
                "interval_seconds": 10,
                "action": "lockdown"
            }
        }


def save_config(config_data):
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)


config = load_config()
tickets = {}
ticket_counter = 0  # счётчик тикетов


# ================== INTENTS / BOT ==================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)


# ================== УТИЛИТЫ ==================

def check_cooldown(user_id: int, command_name: str, cooldown_time: int = 5) -> bool:
    current_time = asyncio.get_event_loop().time()
    key = f"{user_id}_{command_name}"
    if key in COMMAND_COOLDOWN:
        if current_time - COMMAND_COOLDOWN[key] < cooldown_time:
            return False
    COMMAND_COOLDOWN[key] = current_time
    return True


# ================== АНТИСПАМ ==================

async def handle_antispam(message: discord.Message):
    cfg = config.get("antispam", {})
    if not cfg.get("enabled", False):
        return

    if message.author.bot:
        return

    guild = message.guild
    if guild is None:
        return

    if message.author.id == OWNER_ID:
        return
    user_roles = [r.id for r in message.author.roles]
    if any(role_id in user_roles for role_id in ADMIN_ROLES):
        return

    max_msgs = int(cfg.get("messages_per_interval", 5))
    interval = int(cfg.get("interval_seconds", 7))
    mute_seconds = int(cfg.get("mute_seconds", 300))

    now = asyncio.get_event_loop().time()
    uid = message.author.id

    if uid not in user_message_log:
        user_message_log[uid] = []

    user_message_log[uid] = [t for t in user_message_log[uid] if now - t <= interval]
    user_message_log[uid].append(now)

    if len(user_message_log[uid]) > max_msgs:
        if uid in muted_users:
            return

        muted_users.add(uid)

        mute_role = None
        if MUTE_ROLE_ID:
            mute_role = guild.get_role(MUTE_ROLE_ID)

        try:
            if mute_role:
                await message.author.add_roles(mute_role, reason="Авто-мут за спам")
            else:
                await message.author.timeout(
                    discord.utils.utcnow() + discord.timedelta(seconds=mute_seconds),
                    reason="Авто-мут за спам"
                )

            try:
                await message.channel.send(
                    f"{message.author.mention} вы были автоматически замьючены за спам."
                )
            except:
                pass
        except Exception as e:
            print(f"[ANTISPAM] Не удалось замьютить {message.author}: {e}")


# ================== СОБЫТИЯ ==================

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    await handle_antispam(message)

    # Скрытые команды владельца
    if message.author.id == OWNER_ID:
        if message.content.strip() == "!kill_bot":
            print("Команда !kill_bot, выключаю бота")
            await bot.close()
            return

        if message.content.strip().startswith("!Error_bot"):
            parts = message.content.split(" ", 1)
            error_text = parts[1] if len(parts) > 1 else "Неизвестная ошибка"
            try:
                if platform.system() == "Windows":
                    import ctypes
                    ctypes.windll.user32.MessageBoxW(
                        0,
                        error_text,
                        "Ошибка приложения",
                        0x10
                    )
            except Exception as e:
                print(f"Не удалось показать системное окно ошибки: {e}")
            print(f"!Error_bot: {error_text}. Выключаю бота...")
            await bot.close()
            return

    await bot.process_commands(message)


@bot.event
async def on_member_join(member: discord.Member):
    antiraid = config.get("antiraid", {})
    if antiraid.get("enabled", False):
        now = asyncio.get_event_loop().time()
        gid = member.guild.id
        joins_per_interval = int(antiraid.get("joins_per_interval", 5))
        interval = int(antiraid.get("interval_seconds", 10))

        if gid not in join_log:
            join_log[gid] = []
        join_log[gid] = [t for t in join_log[gid] if now - t <= interval]
        join_log[gid].append(now)

        if len(join_log[gid]) > joins_per_interval:
            log_channel = member.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(
                    f"⚠ Обнаружен возможный рейд: {len(join_log[gid])} заходов за {interval} секунд."
                )
            try:
                await member.kick(reason="Anti-raid: слишком много заходов за короткое время")
                return
            except:
                pass

    if member.id in config.get('blocked_users', []):
        try:
            await member.kick(reason="Пользователь заблокирован ботом.")
            return
        except:
            pass

    autorole_id = AUTOROLE_ID
    if autorole_id:
        role = member.guild.get_role(autorole_id)
        if role:
            try:
                await member.add_roles(role)
                welcome_channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
                if welcome_channel:
                    welcome_msg = config.get(
                        'welcome_message',
                        'Добро пожаловать на сервер!'
                    )
                    await welcome_channel.send(
                        f"{member.mention}, {welcome_msg}"
                    )
            except:
                pass


@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен! Версия {BOT_VERSION}')
    try:
        await bot.change_presence(activity=discord.Game(name="VertexCloud"))
    except Exception as e:
        print(f"Ошибка установки статуса: {e}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f'Синхронизировано {len(synced)} команд')
    except Exception as e:
        print(f'Ошибка синхронизации: {e}')


# ================== ТЕКСТОВАЯ КОМАНДА !опл ==================

@bot.command(name="опл")
async def opl_command(ctx: commands.Context):
    """
    Команда !опл — высылает реквизиты оплаты в текущий канал.
    Доступна только пользователям с ролями из OPL_PAYMENT_ROLES.
    """
    if ctx.author.bot:
        return

    user_role_ids = [role.id for role in ctx.author.roles]
    if not any(rid in user_role_ids for rid in OPL_PAYMENT_ROLES):
        await ctx.reply("У вас нет прав для использования этой команды.", mention_author=False)
        return

    text = (
        "**Российская карта:**\n"
        "https://yoomoney.ru/prepaid?from=main-page\n"
        "Номер карты: `4100118483222468`\n"
        "Имя на карте: `YOOMONEY VIRTUAL`\n\n"
        "**Украинская карта:**\n"
        "Номер карты: `5168 7521 1708 7786`\n"
        "Имя на карте: `PRIVAT BANK`\n\n"
        "**Инструкция по переводу на российскую карту:**\n"
        "1. Перейдите по [ссылке](https://yoomoney.ru/prepaid?from=main-page)\n"
        "2. Введите сумму, которую вам нужно перевести, в первом окне.\n"
        "3. Выберите перевод с российской карты и введите данные своей карты.\n"
        "4. После открытия окна с подтверждением введите код списания и отправьте чек об оплате."
    )

    await ctx.send(text)


# ================== СЛЭШ-КОМАНДЫ АДМИНА ==================

@bot.tree.command(
    name="set_welcome",
    description="Установить приветственное сообщение",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(message="Приветственное сообщение")
async def set_welcome(interaction: discord.Interaction, message: str):
    try:
        await interaction.response.defer(ephemeral=True)
        user_roles = [role.id for role in interaction.user.roles]
        if not any(role_id in user_roles for role_id in ADMIN_ROLES):
            await interaction.followup.send("У вас нет прав для использования этой команды.", ephemeral=True)
            return
        if not check_cooldown(interaction.user.id, "set_welcome", 3):
            await interaction.followup.send("Подождите 3 секунды перед повторным использованием команды.", ephemeral=True)
            return
        config['welcome_message'] = message
        save_config(config)
        embed = discord.Embed(
            title="Приветствие обновлено",
            description=f"Новое приветственное сообщение:\n\n> {message}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {str(e)}", ephemeral=True)


@bot.tree.command(
    name="reload_config",
    description="Перезагрузить конфигурацию из config.json",
    guild=discord.Object(id=GUILD_ID)
)
async def reload_config_cmd(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        user_roles = [role.id for role in interaction.user.roles]
        if not any(role_id in user_roles for role_id in ADMIN_ROLES):
            await interaction.followup.send("У вас нет прав для использования этой команды.", ephemeral=True)
            return
        global config
        config = load_config()
        await interaction.followup.send("Конфигурация перезагружена из config.json", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {e}", ephemeral=True)


@bot.tree.command(
    name="admin_panel",
    description="Открыть админ-панель",
    guild=discord.Object(id=GUILD_ID)
)
async def admin_panel(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        user_roles = [role.id for role in interaction.user.roles]
        if not any(role_id in user_roles for role_id in ADMIN_ROLES):
            await interaction.followup.send(
                "У вас нет прав для использования этой команды.",
                ephemeral=True
            )
            return
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
        autorole = guild.get_role(AUTOROLE_ID)
        embed = discord.Embed(
            title="Админ-панель",
            description="Основные настройки и статус бота.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Автороль",
            value=f"{autorole.mention if autorole else 'Не найдена'} (ID: `{AUTOROLE_ID}`)",
            inline=False
        )
        embed.add_field(
            name="Канал приветствий",
            value=f"{welcome_channel.mention if welcome_channel else 'Не найден'} (ID: `{WELCOME_CHANNEL_ID}`)",
            inline=False
        )
        embed.add_field(
            name="Категория тикетов",
            value=f"{category.name if category else 'Не найдена'} (ID: `{TICKET_CATEGORY_ID}`)",
            inline=False
        )
        embed.add_field(
            name="Канал логов",
            value=f"{log_channel.mention if log_channel else 'Не найден'} (ID: `{LOG_CHANNEL_ID}`)",
            inline=False
        )
        embed.add_field(
            name="Заблокированные пользователи",
            value=f"{len(config.get('blocked_users', []))}",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {str(e)}", ephemeral=True)


@bot.tree.command(
    name="commands",
    description="Показать все доступные команды",
    guild=discord.Object(id=GUILD_ID)
)
async def commands_list(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Команды бота",
            description="Список основных команд и возможностей.",
            color=discord.Color.blue()
        )
        user_roles = [role.id for role in interaction.user.roles]
        is_admin = any(role_id in user_roles for role_id in ADMIN_ROLES)
        embed.add_field(
            name="🎫 Тикеты",
            value=(
                "`/ticket_panel` — создать панель тикетов.\n"
                "Кнопка **Создать тикет** — открыть форму обращения.\n"
                "Кнопка **Закрыть тикет** — закрывает канал через 5 секунд."
            ),
            inline=False
        )
        embed.add_field(
            name="🔧 Утилиты",
            value=(
                "`/check_roles` — ваши роли и доступ.\n"
                "`/debug_info` — проверка настроек бота.\n"
                "`/vertexcloud` — приглашение на VertexCloud.\n"
                "`/reload_config` — перезагрузить config.json."
            ),
            inline=False
        )
        if is_admin:
            embed.add_field(
                name="👑 Админ-команды",
                value=(
                    "`/admin_panel` — настройки и статус бота.\n"
                    "`/set_welcome` — изменить приветствие.\n"
                    "`/clear amount:<число>` — очистка сообщений.\n"
                    "`/sync_commands` — пересинхронизация слеш-команд.\n"
                    "`/send_to_channel` — отправка сообщения от бота."
                ),
                inline=False
            )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Ошибка: {str(e)}", ephemeral=True)


# ================== ТИКЕТ-СИСТЕМА ==================

class CloseTicketButton(Button):
    def __init__(self, ticket_id: str):
        super().__init__(
            label="Закрыть тикет",
            style=discord.ButtonStyle.danger,
            custom_id=f"close_ticket_{ticket_id}"
        )
        self.ticket_id = ticket_id

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild
        mod_role = guild.get_role(MOD_ROLE_ID)

        ticket_info = tickets.get(self.ticket_id)
        if not ticket_info:
            await interaction.response.send_message(
                "Информация о тикете не найдена.",
                ephemeral=True
            )
            return

        is_owner = (ticket_info['user_id'] == user.id)
        is_staff = mod_role in user.roles if mod_role else False

        if not (is_owner or is_staff):
            await interaction.response.send_message(
                "Закрыть тикет может только его создатель или персонал.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "Тикет будет закрыт через 5 секунд.",
            ephemeral=True
        )

        channel = interaction.channel

        # логируем
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="Тикет закрыт",
                description=f"Тикет `{self.ticket_id}` будет удалён.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Кто закрыл",
                value=f"{user.mention}",
                inline=False
            )
            await log_channel.send(embed=embed)

        try:
            await channel.send("🔒 Тикет закрывается через 5 секунд...")
        except:
            pass

        await asyncio.sleep(5)

        try:
            if self.ticket_id in tickets:
                del tickets[self.ticket_id]
            await channel.delete()
        except Exception as e:
            print(f"[TICKET] Ошибка удаления канала: {e}")


class ShowTranscriptButton(Button):
    def __init__(self, ticket_id: str):
        super().__init__(
            label="Показать переписку",
            style=discord.ButtonStyle.secondary,
            custom_id=f"transcript_{ticket_id}"
        )
        self.ticket_id = ticket_id

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            channel = interaction.channel
            messages = []
            async for msg in channel.history(limit=None, oldest_first=True):
                if msg.content:
                    messages.append(
                        f"[{msg.created_at.strftime('%H:%M:%S')}] {msg.author.display_name}: {msg.content}"
                    )
            transcript = "\n".join(messages)
            token = hashlib.md5(
                f"{self.ticket_id}_{interaction.user.id}_{len(messages)}".encode()
            ).hexdigest()[:16]
            embed = discord.Embed(
                title="Переписка тикета",
                color=discord.Color.blue()
            )
            if len(transcript) > 4000:
                embed.description = (
                    f"Тикет: `{self.ticket_id}`\n\n"
                    f"Первая часть переписки:\n```{transcript[:2000]}```"
                )
            else:
                embed.description = (
                    f"Тикет: `{self.ticket_id}`\n\n"
                    f"Переписка:\n```{transcript}```"
                )
            embed.add_field(
                name="Токен",
                value=f"`{token}`",
                inline=False
            )
            embed.set_footer(text=f"Всего сообщений: {len(messages)}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Ошибка: {str(e)}", ephemeral=True)


class TicketControlView(View):
    def __init__(self, ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.add_item(CloseTicketButton(ticket_id))
        self.add_item(ShowTranscriptButton(ticket_id))


class TicketModal(Modal, title='Создание тикета'):
    def __init__(self, category: str):
        super().__init__()
        self.category = category

    hosting_nick = TextInput(
        label='Ник на хостинге',
        placeholder='Введите ваш никнейм',
        required=True,
        style=discord.TextStyle.short,
        max_length=50
    )

    problem_description = TextInput(
        label='Описание проблемы',
        placeholder='Подробно опишите вашу проблему...',
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            global ticket_counter
            ticket_counter += 1
            number = ticket_counter  # 1, 2, 3 ...

            # название услуги = категория без пробелов
            service_name = self.category.replace(" ", "-")

            # ИМЯ КАНАЛА БЕЗ НИКА: 🎟️・Категория-номер
            ticket_id = f"🎟️・{service_name}-{number}"

            user = interaction.user
            guild = interaction.guild
            category = guild.get_channel(TICKET_CATEGORY_ID)
            if not category or category.type != discord.ChannelType.category:
                await interaction.followup.send(
                    "Категория для тикетов не найдена, проверьте ID категории.",
                    ephemeral=True
                )
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_channels=True
                )
            }

            mod_role = guild.get_role(MOD_ROLE_ID)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True
                )

            ticket_channel = await guild.create_text_channel(
                name=ticket_id,
                category=category,
                overwrites=overwrites,
                topic=f"Тикет #{number} от {user.display_name} | Категория: {self.category}"
            )

            tickets[ticket_id] = {
                'user_id': user.id,
                'channel_id': ticket_channel.id,
                'category': self.category,
                'hosting_nick': self.hosting_nick.value,
                'problem': self.problem_description.value,
                'moderator_id': None,
                'number': number
            }

            # embed в самом тикет-канале
            embed = discord.Embed(
                title=f"Новый тикет #{number} • {self.category}",
                color=discord.Color.from_rgb(88, 101, 242)
            )
            embed.add_field(
                name="👤 Пользователь",
                value=f"{user.mention} (`{user.display_name}`)",
                inline=False
            )
            embed.add_field(
                name="🧾 Ник на хостинге",
                value=self.hosting_nick.value,
                inline=False
            )
            embed.add_field(
                name="❓ Проблема",
                value=self.problem_description.value,
                inline=False
            )

            await ticket_channel.send(
                f"{user.mention}, ваш тикет создан. Ожидайте ответа персонала.",
                embed=embed,
                view=TicketControlView(ticket_id)
            )

            # уведомление в лог-канал
            log_channel = guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                mod_embed = discord.Embed(
                    title=f"📨 Новый тикет #{number}",
                    color=discord.Color.from_rgb(252, 211, 77)
                )
                mod_embed.add_field(
                    name="📎 Канал",
                    value=f"{ticket_channel.mention}",
                    inline=False
                )
                mod_embed.add_field(
                    name="📂 Категория",
                    value=self.category,
                    inline=False
                )
                mod_embed.add_field(
                    name="👤 Пользователь",
                    value=f"{user.mention} (`{user.display_name}`)",
                    inline=False
                )
                mod_embed.add_field(
                    name="🧾 Ник на хостинге",
                    value=self.hosting_nick.value,
                    inline=False
                )
                mod_embed.add_field(
                    name="❓ Проблема",
                    value=(
                        self.problem_description.value[:400] + "..."
                        if len(self.problem_description.value) > 400
                        else self.problem_description.value
                    ),
                    inline=False
                )
                await log_channel.send(
                    content="Новый заказ / тикет:",
                    embed=mod_embed
                )

            await interaction.followup.send(
                f"Тикет `#{number}` успешно создан. Канал: {ticket_channel.mention}",
                ephemeral=True
            )
        except Exception as e:
            try:
                await interaction.followup.send(
                    f"Произошла ошибка: {str(e)}",
                    ephemeral=True
                )
            except:
                pass


class TicketCategorySelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Технический вопрос",
                description="Проблемы с сервером, хостингом.",
                emoji="🔧"
            ),
            discord.SelectOption(
                label="Финансовый вопрос",
                description="Вопросы по оплате.",
                emoji="💰"
            ),
            discord.SelectOption(
                label="Сотрудничество",
                description="Вопросы по сотрудничеству.",
                emoji="🤝"
            ),
            discord.SelectOption(
                label="Консультация",
                description="Советы и консультации.",
                emoji="📩"
            ),
            discord.SelectOption(
                label="Другое",
                description="Все остальные вопросы.",
                emoji="📌"
            )
        ]
        super().__init__(
            placeholder="Выберите категорию обращения...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        modal = TicketModal(category)
        await interaction.response.send_modal(modal)


class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


class TicketButton(Button):
    def __init__(self):
        super().__init__(
            label="Создать тикет",
            style=discord.ButtonStyle.success,
            custom_id="create_ticket"
        )

    async def callback(self, interaction: discord.Interaction):
        view = TicketView()
        await interaction.response.send_message(
            "Выберите категорию вашего обращения:",
            view=view,
            ephemeral=True
        )


@bot.tree.command(
    name="ticket_panel",
    description="Создать панель для создания тикетов",
    guild=discord.Object(id=GUILD_ID)
)
async def ticket_panel(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Служба поддержки",
            description=(
                "Нужна помощь? Нажмите кнопку ниже, чтобы создать тикет.\n"
                "Опишите проблему — персонал свяжется с вами в личном канале."
            ),
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.add_field(
            name="Как это работает:",
            value=(
                "1. Нажмите **Создать тикет**.\n"
                "2. Выберите категорию обращения.\n"
                "3. Заполните форму.\n"
                "4. Ожидайте ответа персонала."
            ),
            inline=False
        )

        view = View(timeout=None)
        view.add_item(TicketButton())
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send(
            "Панель тикетов успешно создана.",
            ephemeral=True
        )
    except Exception as e:
        try:
            await interaction.followup.send(
                f"Произошла ошибка: {str(e)}",
                ephemeral=True
            )
        except:
            pass


# ================== ПРОЧИЕ КОМАНДЫ ==================

@bot.tree.command(
    name="debug_info",
    description="Показать информацию о настройках бота",
    guild=discord.Object(id=GUILD_ID)
)
async def debug_info(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        mod_role = guild.get_role(MOD_ROLE_ID)
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        embed = discord.Embed(
            title="Debug информация",
            color=discord.Color.orange()
        )
        value_cat = f"ID: `{TICKET_CATEGORY_ID}`\nНайдена: {'✅' if category else '❌'}"
        if category:
            value_cat += f"\nТип: `{category.type}`"
        embed.add_field(
            name="Категория тикетов",
            value=value_cat,
            inline=False
        )
        embed.add_field(
            name="Роль модератора",
            value=(
                f"ID: `{MOD_ROLE_ID}`\nНайдена: {'✅' if mod_role else '❌'}"
            ),
            inline=False
        )
        embed.add_field(
            name="Канал логов",
            value=(
                f"ID: `{LOG_CHANNEL_ID}`\nНайден: {'✅' if log_channel else '❌'}"
            ),
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        try:
            await interaction.followup.send(
                f"Произошла ошибка: {str(e)}",
                ephemeral=True
            )
        except:
            pass


@bot.tree.command(
    name="check_roles",
    description="Проверить ваши роли и доступ",
    guild=discord.Object(id=GUILD_ID)
)
async def check_roles(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        user_roles = [role.id for role in interaction.user.roles]
        admin_access = any(role_id in user_roles for role_id in ADMIN_ROLES)
        embed = discord.Embed(
            title="Ваши роли",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Админ-доступ",
            value="✅ Есть" if admin_access else "❌ Нет",
            inline=False
        )
        embed.add_field(
            name="Список ролей",
            value="\n".join(
                [f"• {role.mention} (`{role.id}`)" for role in interaction.user.roles]
            ) or "Нет ролей",
            inline=False
        )
        embed.add_field(
            name="Требуемые ID админ-ролей",
            value="\n".join([f"• `{role_id}`" for role_id in ADMIN_ROLES]),
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        try:
            await interaction.followup.send(
                f"Произошла ошибка: {str(e)}",
                ephemeral=True
            )
        except:
            pass


@bot.tree.command(
    name="clear",
    description="Очистить сообщения в текущем канале",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(amount="Сколько сообщений удалить (1-100)")
async def clear_messages(interaction: discord.Interaction, amount: int):
    try:
        await interaction.response.defer(ephemeral=True)
        if amount < 1 or amount > 100:
            await interaction.followup.send(
                "Укажите число от 1 до 100.",
                ephemeral=True
            )
            return
        user_roles = [role.id for role in interaction.user.roles]
        if not any(role_id in user_roles for role_id in ADMIN_ROLES):
            await interaction.followup.send(
                "У вас нет прав для использования этой команды.",
                ephemeral=True
            )
            return
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(
            f"Удалено сообщений: {len(deleted)}",
            ephemeral=True
        )
    except Exception as e:
        try:
            await interaction.followup.send(
                f"Ошибка очистки: {str(e)}",
                ephemeral=True
            )
        except:
            pass


@bot.tree.command(
    name="sync_commands",
    description="Пересинхронизировать слеш-команды",
    guild=discord.Object(id=GUILD_ID)
)
async def sync_commands(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
        user_roles = [role.id for role in interaction.user.roles]
        if not any(role_id in user_roles for role_id in ADMIN_ROLES):
            await interaction.followup.send(
                "У вас нет прав для использования этой команды.",
                ephemeral=True
            )
            return
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await interaction.followup.send(
            f"Синхронизировано команд: {len(synced)}",
            ephemeral=True
        )
    except Exception as e:
        try:
            await interaction.followup.send(
                f"Ошибка синхронизации: {str(e)}",
                ephemeral=True
            )
        except:
            pass


@bot.tree.command(
    name="send_to_channel",
    description="Отправить сообщение от бота в указанный канал",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(
    channel="Канал, куда отправить сообщение",
    text="Текст сообщения"
)
async def send_to_channel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    text: str
):
    try:
        await interaction.response.defer(ephemeral=True)
        user_roles = [role.id for role in interaction.user.roles]
        if not any(role_id in user_roles for role_id in ADMIN_ROLES):
            await interaction.followup.send(
                "У вас нет прав для использования этой команды.",
                ephemeral=True
            )
            return
        await channel.send(text)
        await interaction.followup.send(
            f"Сообщение отправлено в {channel.mention}.",
            ephemeral=True
        )
    except Exception as e:
        try:
            await interaction.followup.send(
                f"Ошибка отправки: {str(e)}",
                ephemeral=True
            )
        except:
            pass


class VertexButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Перейти на VertexCloud",
                style=discord.ButtonStyle.link,
                url="https://discord.gg/qgUgPPMcKJ"
            )
        )


@bot.tree.command(
    name="vertexcloud",
    description="Отправить красивое приглашение на VertexCloud",
    guild=discord.Object(id=GUILD_ID)
)
async def vertexcloud_cmd(interaction: discord.Interaction):
    try:
        embed = discord.Embed(
            title="VertexCloud",
            description="Нажмите на кнопку ниже, чтобы перейти на сервер VertexCloud.",
            color=discord.Color.blurple()
        )
        view = VertexButtonView()
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=False
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Ошибка: {str(e)}",
            ephemeral=True
        )


# ================== ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК SLASH ==================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):
    try:
        await interaction.response.send_message(
            f"Произошла ошибка при выполнении команды: `{error}`",
            ephemeral=True
        )
    except discord.InteractionResponded:
        try:
            await interaction.followup.send(
                f"Произошла ошибка при выполнении команды: `{error}`",
                ephemeral=True
            )
        except:
            pass


# ================== ФУНКЦИЯ ЗАПУСКА ==================

def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    run_bot()

