import os

# --- Основные настройки ---
TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"  # Токен бота из Discord Developer Portal
GUILD_ID = 123456789012345678  # ID вашего сервера Zarion

# --- Дизайн ---
EMBED_COLOR = 0x60AEC0  # Цвет полоски #60aec0
SERVER_NAME = "Zarion"
SERVER_AVATAR_URL = "https://i.imgur.com/example.gif"  # Ссылка на гиф/аватарку или None

# --- Роли Администрации ---
ROLE_ADMIN_1_ID = 111111111111111111  # Первичная роль админа
ROLE_ADMIN_2_ID = 222222222222222222  # Вторичная роль админа
ROLE_SUPPORT_ID = 333333333333333333  # Роль Support
ROLE_CREATIVE_ID = 444444444444444444 # Роль Creative

# --- Категории и Канал ---
CATEGORY_STAFF_ID = 555555555555555555  # Категория Staff
CATEGORY_EVENT_ID = 666666666666666666  # Категория Event

CHANNEL_REQ_ID = 777777777777777777    # #req (Заявки)
CHANNEL_LOGS_ID = 888888888888888888   # #logs (Логи)
CHANNEL_APPLY_ID = 999999999999999999  # Канал, где висит сообщение подачи заявок

# --- Настройки Экономики ---
COINS_PER_MESSAGE = 2
COINS_PER_VOICE_MINUTE = 5
EVENT_REWARD_COINS = 1000

COST_CUSTOM_ROLE = 2000
COST_PRIVATE_VOICE = 10000
TRANSFER_TAX_RATE = 0.02  # 2% комиссия

# --- Настройки Игр ---
DUCK_MSG_THRESHOLD = 50   # Сообщений в час для спавна утки
DUCK_REWARD_COINS = 100   # Награда за утку