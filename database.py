import aiosqlite

DB_NAME = "zarion.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                warns INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT coins, warns FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id, coins, warns) VALUES (?, 0, 0)", (user_id,))
                await db.commit()
                return {"coins": 0, "warns": 0}
            return {"coins": row[0], "warns": row[1]}

async def add_coins(user_id: int, amount: int):
    await get_user(user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def remove_coins(user_id: int, amount: int) -> bool:
    user = await get_user(user_id)
    if user["coins"] < amount:
        return False
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
    return True

async def add_warn(user_id: int) -> int:
    await get_user(user_id)
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET warns = warns + 1 WHERE user_id = ?", (user_id,))
        await db.commit()
        async with db.execute("SELECT warns FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0]

async def reset_warns(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET warns = 0 WHERE user_id = ?", (user_id,))
        await db.commit()